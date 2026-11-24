#!/usr/bin/env python3
"""Per-command reference hook: preserve repository hooks and validate a PR branch deletion."""

import os
import subprocess
import sys
from pathlib import Path

from finish_pr import FinishError, ref_sha, save_state, worktrees


def main():
    phase = sys.argv[1]
    payload = sys.stdin.buffer.read()
    ref = os.environ["CODEX_PR_DELETE_REF"]
    expected = os.environ["CODEX_PR_DELETE_SHA"]
    rows = [line.split() for line in payload.decode().splitlines()]
    deleting = any(len(row) == 3 and row[2] == ref and set(row[1]) == {"0"} for row in rows)
    # A committed receipt proves deletion happened even if the caller never checkpoints it.
    if deleting and phase == "committed":
        save_state(
            Path(os.environ["CODEX_PR_DELETE_RECEIPT"]),
            {
                "token": os.environ["CODEX_PR_DELETE_TOKEN"],
                "ref": ref,
                "sha": expected,
            },
        )
    original = os.environ.get("CODEX_PR_ORIGINAL_REF_HOOK")
    if original and os.access(original, os.X_OK):
        result = subprocess.run([original, phase], input=payload, check=False, timeout=30)
        if result.returncode:
            return result.returncode
    if deleting and phase == "prepared":
        # Git has locked the ref. Read its actual value: native deletion may pass zero as old OID.
        if ref_sha(".", ref) != expected:
            print("PR source changed before deletion; preserving branch", file=sys.stderr)
            return 1
        if any(branch == ref for _, branch in worktrees(".")):
            print("PR source is in use by a worktree; preserving branch", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FinishError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"PR deletion guard failed: {error}", file=sys.stderr)
        raise SystemExit(1)
