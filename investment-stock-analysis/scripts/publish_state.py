#!/usr/bin/env python3
"""Serialize local research-state commits; semantic/template checks remain external."""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time


class Rejected(Exception):
    """Expected refusal, with a stable CLI exit code for recovery decisions."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def digest(data):
    """The token covers the entire original file, not just its version label."""
    return 'absent' if data is None else hashlib.sha256(data).hexdigest()


def timestamp(value):
    """Reject ambiguous local times instead of guessing a timezone."""
    try:
        result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError('timezone required')
        return result
    except ValueError as exc:
        raise Rejected(5, 'Research cutoff must be timezone-aware ISO 8601') from exc


def cutoff(data):
    """Read the one business field required for monotonic state publication."""
    values = re.findall(r'^- 研究截止：(.*)$', data.decode('utf-8'), re.M)
    if len(values) != 1:
        raise Rejected(5, 'Exactly one research cutoff field is required')
    return timestamp(values[0].strip())


@contextlib.contextmanager
def company_lock(directory, timeout):
    """Hold an OS-managed lock across comparison, replacement and readback."""
    # Keep this inode permanently: unlinking it would split the lock domain.
    with (directory / '.state.lock').open('a+b') as lock:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Rejected(4, 'Company state lock timed out')
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def publish(directory, candidate, expected, timeout=5, normalize_time=None):
    """Commit a previously validated candidate using a locked compare-and-swap.

    This does not validate evidence, index links or baseline eligibility.
    Legacy time normalization requires an externally verified equivalent instant.
    """
    directory = Path(directory).resolve(strict=True)
    state = directory / 'state.md'
    if state.is_symlink() or (directory / '.state.lock').is_symlink():
        raise ValueError('State and lock must not be symbolic links')
    if not 0 <= timeout <= 60:
        raise ValueError('Lock timeout must be between 0 and 60 seconds')
    proposed = Path(candidate).read_bytes() if candidate is not None else None
    with company_lock(directory, timeout):
        current = state.read_bytes() if state.exists() else None
        if digest(current) != expected:
            raise Rejected(3, 'State changed: reload, reconcile and revalidate before retry')
        if normalize_time is not None:
            # Restrict migration to this field; never accept a replacement document.
            timestamp(normalize_time)
            if current is None:
                raise Rejected(5, 'Cannot normalize absent state')
            try:
                cutoff(current)
            except Rejected:
                pass
            else:
                raise Rejected(5, 'Already normalized: use the ordinary commit path')
            content, count = re.subn(r'^- 研究截止：.*$', '- 研究截止：' + normalize_time,
                                     current.decode('utf-8'), flags=re.M)
            if count != 1:
                raise Rejected(5, 'Cannot normalize missing or duplicate cutoff')
            proposed = content.encode('utf-8')
        else:
            if proposed is None:
                raise ValueError('Candidate required')
            new_time = cutoff(proposed)
            if current is not None and new_time < cutoff(current):
                raise Rejected(5, 'Research cutoff regression: archive without applying')
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.state-write-', suffix='.tmp', dir=directory)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(proposed)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, state)
            temporary = None
            folder_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(folder_fd)
            finally:
                os.close(folder_fd)
            actual = state.read_bytes()
            if actual != proposed:
                raise RuntimeError('Readback mismatch: inspect state before retrying')
            return digest(actual)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)


def main():
    """Expose recovery-relevant failures without treating them as successful saves."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--candidate')
    source.add_argument('--normalize-time', help='Evidence-verified encoding of the existing cutoff only')
    parser.add_argument('--expected', required=True, help='SHA-256 of original state bytes, or absent')
    parser.add_argument('--timeout', type=float, default=5)
    args = parser.parse_args()
    try:
        result = publish(args.directory, args.candidate, args.expected, args.timeout, args.normalize_time)
    except Rejected as exc:
        print(json.dumps({'error': str(exc), 'code': exc.code}, ensure_ascii=False))
        return exc.code
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc), 'code': 1,
                          'recovery': 'Inspect current state before retrying; replacement may have completed'},
                         ensure_ascii=False))
        return 1
    print(json.dumps({'committed_sha256': result}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
