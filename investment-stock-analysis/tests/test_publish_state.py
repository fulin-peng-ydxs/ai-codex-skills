"""Local filesystem/process tests; no financial data or real research archives."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/publish_state.py'
spec = importlib.util.spec_from_file_location('publisher', SCRIPT)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def body(date, version):
    return f'# 合成状态\n\n- 研究截止：{date}\n- 状态版本：{version}\n'.encode()


class StatePublication(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.gettempdir()) / 'ai-agent/ai-codex-skills'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='state-test-', dir=base)
        self.root = Path(self.temp.name)
        self.company = self.root / 'company'
        self.company.mkdir()
        self.state = self.company / 'state.md'
        self.old = body('2026-11-01T10:00:00+08:00', 'v1')
        self.new = body('2026-11-23T10:00:00+08:00', 'v2')
        self.state.write_bytes(self.old)
        self.candidate = self.root / 'candidate.md'
        self.candidate.write_bytes(self.new)
        self.hash = publisher.digest(self.old)

    def tearDown(self):
        self.temp.cleanup()

    def command(self, candidate=None, expected=None):
        return [sys.executable, '-B', str(SCRIPT), '--directory', str(self.company),
                '--candidate', str(candidate or self.candidate), '--expected', expected or self.hash]

    def run_cli(self, *extra, expected=None):
        return subprocess.run(self.command(expected=expected) + list(extra), capture_output=True, text=True)

    def test_commit_and_readback(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_bytes(), self.new)
        self.assertIn(hashlib.sha256(self.new).hexdigest(), result.stdout)

    def test_absent_and_duplicate_creation(self):
        self.state.unlink()
        self.assertEqual(self.run_cli(expected='absent').returncode, 0)
        self.assertEqual(self.run_cli(expected='absent').returncode, 3)
        self.assertEqual(self.state.read_bytes(), self.new)

    def test_stale_candidate_preserves_newer_state(self):
        self.state.write_bytes(self.new)
        self.assertEqual(self.run_cli().returncode, 3)
        self.assertEqual(self.state.read_bytes(), self.new)

    def test_two_competing_processes_only_one_commits(self):
        second = self.root / 'second.md'
        second_data = body('2026-11-24T10:00:00+08:00', 'v3')
        second.write_bytes(second_data)
        processes = [subprocess.Popen(self.command(c), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for c in [self.candidate, second]]
        for proc in processes:
            proc.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 3])
        self.assertIn(self.state.read_bytes(), [self.new, second_data])

    def test_old_cutoff_rejected_even_with_current_hash(self):
        self.candidate.write_bytes(body('2023-12-31T23:59:59+08:00', 'historical'))
        self.assertEqual(self.run_cli().returncode, 5)
        self.assertEqual(self.state.read_bytes(), self.old)

    def test_conflict_recovery_retains_both_reconciled_records(self):
        first = self.new + b'\nrecord-A\n'
        self.candidate.write_bytes(first)
        self.assertEqual(self.run_cli().returncode, 0)
        self.candidate.write_bytes(self.new + b'\nrecord-B\n')
        self.assertEqual(self.run_cli().returncode, 3)
        # The caller reloads and reconciles; the publisher must not invent a merge.
        latest = self.state.read_bytes()
        merged = latest + b'record-B\n'
        self.candidate.write_bytes(merged)
        self.assertEqual(self.run_cli(expected=publisher.digest(latest)).returncode, 0)
        self.assertEqual(self.state.read_bytes(), merged)

    def test_same_cutoff_revision_allowed(self):
        corrected = body('2026-11-01T02:00:00Z', 'corrected')
        self.candidate.write_bytes(corrected)
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.state.read_bytes(), corrected)

    def test_missing_timezone_rejected(self):
        self.candidate.write_bytes(body('2026-11-23T10:00:00', 'bad'))
        self.assertEqual(self.run_cli().returncode, 5)
        self.assertEqual(self.state.read_bytes(), self.old)

    def test_legacy_time_requires_evidence_based_normalization(self):
        old = body('2026年11月1日10时（北京时间）', 'legacy')
        self.state.write_bytes(old)
        expected = publisher.digest(old)
        self.assertEqual(self.run_cli(expected=expected).returncode, 5)
        command = [sys.executable, '-B', str(SCRIPT), '--directory', str(self.company),
                   '--normalize-time', '2026-11-01T10:00:00+08:00', '--expected', expected]
        result = subprocess.run(command, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = body('2026-11-01T10:00:00+08:00', 'legacy')
        self.assertEqual(self.state.read_bytes(), normalized)
        command[-1] = publisher.digest(normalized)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 5)

    def test_live_lock_timeout_and_process_death_release(self):
        code = """import importlib.util,sys,time
from pathlib import Path
s=importlib.util.spec_from_file_location('p',sys.argv[1]);p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
with p.company_lock(Path(sys.argv[2]),1):
 print('locked',flush=True)
 time.sleep(30)
"""
        proc = subprocess.Popen([sys.executable, '-B', '-c', code, str(SCRIPT), str(self.company)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), 'locked')
            inode = (self.company / '.state.lock').stat().st_ino
            self.assertEqual(self.run_cli('--timeout', '0.1').returncode, 4)
            self.assertEqual(self.state.read_bytes(), self.old)
        finally:
            proc.kill()
            proc.wait(timeout=5)
            proc.stdout.close()
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual((self.company / '.state.lock').stat().st_ino, inode)

    def crash(self, after_replace):
        code = """import importlib.util,sys,os
s=importlib.util.spec_from_file_location('p',sys.argv[1]);p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
real=p.os.replace
def crash(a,b):
 if sys.argv[5]=='after': real(a,b)
 os._exit(9)
p.os.replace=crash
p.publish(sys.argv[2],sys.argv[3],sys.argv[4])
"""
        result = subprocess.run([sys.executable, '-B', '-c', code, str(SCRIPT), str(self.company),
                                 str(self.candidate), self.hash, 'after' if after_replace else 'before'])
        self.assertEqual(result.returncode, 9)

    def test_crash_before_replace_preserves_state_and_retry_works(self):
        self.crash(False)
        self.assertEqual(self.state.read_bytes(), self.old)
        self.assertTrue(list(self.company.glob('.state-write-*.tmp')))
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.state.read_bytes(), self.new)

    def test_response_lost_after_replace_readback_detects_commit(self):
        self.crash(True)
        self.assertEqual(self.state.read_bytes(), self.new)
        self.assertEqual(self.run_cli().returncode, 3)
        self.assertEqual(self.state.read_bytes(), self.new)

    def test_replace_failure_preserves_original_and_cleans_own_temp(self):
        with mock.patch.object(publisher.os, 'replace', side_effect=OSError('injected failure')):
            with self.assertRaises(OSError):
                publisher.publish(self.company, self.candidate, self.hash)
        self.assertEqual(self.state.read_bytes(), self.old)
        self.assertEqual(list(self.company.glob('.state-write-*.tmp')), [])
        self.assertEqual(self.run_cli().returncode, 0)


if __name__ == '__main__':
    unittest.main()
