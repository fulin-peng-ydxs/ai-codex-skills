"""A resumed monitor cannot obtain a new budget through flags or clock changes."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pr_state

IDENTITY = {'url': 'https://github.com/o/r/pull/1', 'head': 'a' * 40}


class BudgetTests(unittest.TestCase):
    def start(self, state, wall=1000, monotonic=50, budget=1800, **options):
        return pr_state.start_wait(state, IDENTITY, budget, 'default', wall, monotonic, **options)

    def test_repository_timeout_gets_queue_headroom_under_one_ceiling(self):
        self.assertEqual(pr_state.choose_budget(), (1800, 'default'))
        self.assertEqual(pr_state.choose_budget(ci_timeout=1800), (2100, 'repository_ci'))
        self.assertEqual(pr_state.choose_budget(ci_timeout=5000), (3600, 'repository_ci'))
        self.assertEqual(pr_state.choose_budget(explicit=60, ci_timeout=1800), (60, 'explicit'))

    def test_resume_uses_remaining_time_not_a_new_timeout_flag(self):
        state = {}
        self.assertEqual(self.start(state), 1850)
        pr_state.checkpoint_wait(state, 1850, 150)
        self.assertEqual(self.start(state, wall=1200, monotonic=250, budget=9999), 1850)
        self.assertEqual(state['watch']['budget_seconds'], 1800)

    def test_clock_rollback_never_grants_extra_time(self):
        state = {}
        self.start(state)
        pr_state.checkpoint_wait(state, 1850, 150)
        self.assertEqual(self.start(state, wall=900, monotonic=250), 1850)
        # A rebooted monotonic clock can consume the saved remainder, never a fresh budget.
        self.assertEqual(self.start(state, wall=1200, monotonic=10), 1610)

    def test_expired_budget_stays_expired_and_only_explicit_extension_adds_time(self):
        state = {}
        self.start(state, budget=10)
        self.assertEqual(self.start(state, wall=1020, monotonic=70), 70)
        self.assertEqual(self.start(state, wall=1020, monotonic=70, extend=30), 100)
        self.assertEqual(state['watch']['extensions'], 1)

    def test_user_deadline_survives_a_real_repair_round_and_default_timeout(self):
        state = {}
        pr_state.start_wait(state, IDENTITY, 60, 'explicit', 1000, 0)
        repaired = dict(IDENTITY, head='b' * 40)
        deadline = pr_state.start_wait(state, repaired, 1800, 'default', 1020, 20, new_round=True)
        self.assertEqual(deadline, 60)
        self.assertEqual(state['watch']['deadline_at'], 1060)
        self.assertEqual(state['watch']['remaining_seconds'], 40)
        self.assertEqual(len(state['watch_history']), 1)

    def test_resumed_smaller_user_limit_shortens_but_cannot_extend_wait(self):
        state = {}
        self.start(state)
        deadline = pr_state.start_wait(state, IDENTITY, 30, 'explicit', 1010, 60)
        self.assertEqual(deadline, 90)
        self.assertEqual(state['watch']['hard_deadline_at'], 1040)
        repaired = dict(IDENTITY, head='b' * 40)
        deadline = pr_state.start_wait(state, repaired, 1800, 'default', 1020, 70, new_round=True)
        self.assertEqual(deadline, 90)

    def test_authorized_extension_is_explicit_even_during_a_new_source_round(self):
        state = {}
        pr_state.start_wait(state, IDENTITY, 10, 'explicit', 1000, 0)
        repaired = dict(IDENTITY, head='b' * 40)
        deadline = pr_state.start_wait(state, repaired, 1800, 'default', 1020, 20,
                                       new_round=True, extend=30)
        self.assertEqual(deadline, 50)
        self.assertEqual(state['watch']['hard_deadline_at'], 1050)

    def test_new_round_requires_changed_source_and_same_pr(self):
        state = {}
        self.start(state)
        with self.assertRaises(ValueError):
            self.start(state, new_round=True)
        changed = dict(IDENTITY, head='b' * 40)
        with self.assertRaises(ValueError):
            pr_state.start_wait(state, changed, 1800, 'default', 1010, 60)
        deadline = pr_state.start_wait(state, changed, 1800, 'default', 1010, 60, new_round=True)
        self.assertEqual(deadline, 1860)
        other = dict(changed, url='https://github.com/o/r/pull/2', head='c' * 40)
        with self.assertRaises(ValueError):
            pr_state.start_wait(state, other, 1800, 'default', 1020, 70, new_round=True)

    def test_invalid_budgets_and_corrupt_saved_state_are_rejected(self):
        for number in (0, -1, True, float('nan'), float('inf')):
            with self.assertRaises((TypeError, ValueError)):
                pr_state.choose_budget(explicit=number)
        state = {}
        self.start(state)
        state['watch']['remaining_seconds'] = 'untrusted'
        with self.assertRaises(ValueError):
            self.start(state)


class StateFileTests(unittest.TestCase):
    def test_atomic_writes_and_private_path_do_not_touch_business_worktree(self):
        parent = Path(os.environ.get('TMPDIR') or tempfile.gettempdir()) / 'ai-agent' / 'codex-skills'
        created = not parent.exists()
        parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix='pr-state-test-', dir=parent) as directory:
                repo = Path(directory)
                subprocess.run(['git', 'init', '-q', str(repo)], check=True)
                path = pr_state.private_path(repo, repo / '.git/codex/pr-push/task.json')
                pr_state.save_state(path, {'phase': 'watching'})
                with patch.object(pr_state.os, 'replace', side_effect=OSError('interrupted')), self.assertRaises(OSError):
                    pr_state.save_state(path, {'phase': 'pending'})
                self.assertEqual(json.loads(path.read_text()), {'phase': 'watching'})
                self.assertEqual(list(path.parent.iterdir()), [path])
                with self.assertRaises(ValueError):
                    pr_state.private_path(repo, repo / 'result.json')
                result = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True)
                self.assertFalse(result)
        finally:
            if created:
                try:
                    parent.rmdir()
                except OSError:
                    pass


if __name__ == '__main__':
    unittest.main()
