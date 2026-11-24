"""Real Git regression cases for interrupted finalization and safe-ahead return branches."""

import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "finish_pr", Path(__file__).resolve().parents[1] / "scripts" / "finish_pr.py"
)
finisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finisher)


class FinishTests(unittest.TestCase):
    def setUp(self):
        self.parent = (
            Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / "ai-agent" / "codex-skills"
        )
        self.created = [p for p in (self.parent.parent, self.parent) if not p.exists()]
        self.parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="pr-finish-test-", dir=self.parent)
        self.repo = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()
        for parent in reversed(self.created):
            try:
                parent.rmdir()
            except OSError:
                pass

    def git(self, *args):
        result = subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, (args, result.stderr))
        return result.stdout.strip()

    def fixture(self, original="main"):
        self.git("init", "-b", "main")
        self.git("config", "user.name", "PR finalization test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "remote.origin.url", ".")
        self.git("config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
        (self.repo / "app").write_text("A\n")
        self.git("add", "app")
        self.git("commit", "-m", "A")
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", f"refs/remotes/origin/{original}", self.base)
        if original != "main":
            self.git("switch", "-c", original)
        (self.repo / "app").write_text("B\n")
        self.git("commit", "-am", "B")
        self.original_sha = self.git("rev-parse", "HEAD")
        self.work = "codex/task"
        self.git("switch", "-c", self.work)
        (self.repo / "app").write_text("C repair\n")
        self.git("commit", "-am", "C")
        self.source = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/codex/task", self.source)
        self.git("branch", "--set-upstream-to=origin/codex/task", self.work)
        self.git("switch", "-c", "simulated-server-main", self.base)
        self.git("merge", "--no-ff", self.work, "-m", "PR merged")
        self.merged = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.merged)
        self.git("switch", self.work)
        self.original = original
        self.path = self.repo / ".git" / "codex" / "pr-push" / "example-project-1.json"
        self.path.parent.mkdir(parents=True)
        self.state = {
            "version": 1,
            "phase": "pending",
            "context": {
                "pr_url": "https://github.com/example/project/pull/1",
                "merged_at": "2026-11-24T10:00:00Z",
                "return_branch": original,
                "return_upstream": f"refs/remotes/origin/{original}",
                "return_sha": self.original_sha,
                "work_branch": self.work,
                "source_sha": self.source,
                "target_ref": "refs/remotes/origin/main",
                "merge_sha": self.merged,
                "allowed_commits": [self.original_sha, self.source],
            },
        }
        finisher.save_state(self.path, self.state)

    def finish(self):
        return finisher.finish_pr(self.repo, self.path)

    def assert_complete(self, expected):
        self.assertEqual(self.git("branch", "--show-current"), self.original)
        self.assertEqual(self.git("rev-parse", "HEAD"), expected)
        self.assertFalse(self.git("branch", "--list", self.work))
        self.assertFalse(self.git("status", "--porcelain"))
        self.assertEqual(json.loads(self.path.read_text())["phase"], "complete")
        self.git("merge-base", "--is-ancestor", self.source, "origin/main")

    def interrupt_checkpoint(self, phase):
        save = finisher.save_state

        def write(path, state):
            if state["phase"] == phase:
                raise OSError("simulated process interruption before checkpoint")
            save(path, state)

        with patch.object(finisher, "save_state", side_effect=write):
            with self.assertRaises(OSError):
                self.finish()

    def test_main_sync_and_cleanup(self):
        self.fixture()
        self.assertEqual(self.finish()["sync_mode"], "fast_forward")
        self.assert_complete(self.merged)
        self.assertEqual((self.repo / "app").read_text(), "C repair\n")

    def test_feature_may_remain_safely_ahead_of_its_upstream(self):
        self.fixture("feature")
        # Source upstream may already have been deleted by GitHub after merging.
        self.git("update-ref", "-d", "refs/remotes/origin/codex/task")
        result = self.finish()
        self.assertEqual((result["sync_mode"], result["ahead_count"]), ("ahead", 1))
        self.assertEqual(self.git("rev-parse", "origin/feature"), self.base)
        self.assert_complete(self.original_sha)
        config = subprocess.run(
            ["git", "config", "--get", f"branch.{self.work}.remote"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(config.returncode, 1)

    def test_resume_after_sync_command_before_checkpoint(self):
        self.fixture()
        self.interrupt_checkpoint("synced")
        self.assertEqual(self.git("rev-parse", "main"), self.merged)
        self.assertEqual(json.loads(self.path.read_text())["phase"], "syncing")
        self.finish()
        self.assert_complete(self.merged)

    def test_resume_after_saved_sync_before_cleanup(self):
        self.fixture()
        self.interrupt_checkpoint("cleaning")
        self.assertEqual(json.loads(self.path.read_text())["phase"], "synced")
        self.finish()
        self.assert_complete(self.merged)

    def test_resume_after_ref_deletion_before_complete_checkpoint(self):
        self.fixture()
        self.interrupt_checkpoint("complete")
        self.assertFalse(self.git("branch", "--list", self.work))
        self.assertEqual(json.loads(self.path.read_text())["phase"], "cleaning")
        self.assertEqual(self.finish()["cleanup"], "already_absent")
        self.assert_complete(self.merged)

    def test_repeated_completed_cleanup_does_not_move_or_delete_refs(self):
        self.fixture()
        self.finish()
        before = self.git("show-ref")
        self.assertEqual(self.finish()["cleanup"], "already_complete")
        self.assertEqual(self.git("show-ref"), before)
        self.assert_complete(self.merged)

    def test_recreated_work_branch_is_preserved(self):
        self.fixture()
        self.finish()
        self.git("branch", self.work, self.source)
        with self.assertRaisesRegex(finisher.FinishError, "recreated"):
            self.finish()
        self.assertEqual(self.git("rev-parse", self.work), self.source)

    def test_return_branch_changed_after_sync_is_preserved(self):
        self.fixture()
        self.interrupt_checkpoint("cleaning")
        self.git("commit", "--allow-empty", "-m", "unrelated new work")
        unrelated = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(finisher.FinishError, "return branch changed"):
            self.finish()
        self.assertEqual(self.git("rev-parse", "main"), unrelated)
        self.assertEqual(self.git("rev-parse", self.work), self.source)

    def test_unknown_ahead_commits_are_rejected(self):
        self.fixture("feature")
        self.state["context"]["allowed_commits"] = [self.source]
        finisher.save_state(self.path, self.state)
        with self.assertRaisesRegex(finisher.FinishError, "unapproved"):
            self.finish()
        self.assertEqual(self.git("rev-parse", "feature"), self.original_sha)

    def test_diverged_return_upstream_is_rejected(self):
        self.fixture("feature")
        tree = self.git("rev-parse", f"{self.base}^{{tree}}")
        other = self.git("commit-tree", tree, "-p", self.base, "-m", "upstream diverged")
        self.git("update-ref", "refs/remotes/origin/feature", other)
        with self.assertRaisesRegex(finisher.FinishError, "diverged"):
            self.finish()
        self.assertEqual(self.git("rev-parse", "feature"), self.original_sha)

    def test_missing_merge_evidence_prevents_any_sync(self):
        self.fixture()
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        with self.assertRaisesRegex(finisher.FinishError, "not reachable"):
            self.finish()
        self.assertEqual(self.git("rev-parse", "main"), self.original_sha)

    def test_dirty_files_and_changed_source_are_preserved(self):
        self.fixture()
        (self.repo / "app").write_text("uncommitted work\n")
        with self.assertRaisesRegex(finisher.FinishError, "not clean"):
            self.finish()
        self.git("commit", "-am", "unpublished work")
        new_source = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(finisher.FinishError, "work branch changed"):
            self.finish()
        self.assertEqual(self.git("rev-parse", self.work), new_source)

    def test_source_ref_change_during_cleanup_is_not_deleted(self):
        self.fixture()
        tree = self.git("rev-parse", f"{self.source}^{{tree}}")
        new_source = self.git("commit-tree", tree, "-p", self.source, "-m", "concurrent work")
        real_git = finisher.git

        def race(repo, *arguments, **kwargs):
            if arguments[-4:] == ("branch", "-d", "--", self.work):
                real_git(repo, "update-ref", f"refs/heads/{self.work}", new_source)
            return real_git(repo, *arguments, **kwargs)

        with patch.object(finisher, "git", side_effect=race):
            with self.assertRaises(finisher.FinishError):
                self.finish()
        self.assertEqual(self.git("rev-parse", self.work), new_source)

    def write_reference_hook(self, body):
        script = self.repo / ".git" / "test-reference-hook.py"
        script.write_text(body)
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        hook.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -B {shlex.quote(str(script))} "$@"\n'
        )
        hook.chmod(0o700)

    def test_checkout_race_before_native_deletion_preserves_peer(self):
        self.fixture()
        real_git = finisher.git
        with tempfile.TemporaryDirectory(prefix="pr-peer-race-", dir=self.parent) as peer:
            injected = False

            def race(repo, *arguments, **kwargs):
                nonlocal injected
                if arguments[-4:] == ("branch", "-d", "--", self.work) and not injected:
                    injected = True
                    real_git(self.repo, "worktree", "add", peer, self.work)
                    (Path(peer) / "app").write_text("new uncommitted work\n")
                return real_git(repo, *arguments, **kwargs)

            with patch.object(finisher, "git", side_effect=race):
                with self.assertRaises(finisher.FinishError):
                    self.finish()
            self.assertEqual(real_git(peer, "rev-parse", "HEAD").stdout.strip(), self.source)
            self.assertEqual(self.git("rev-parse", self.work), self.source)
            self.assertEqual((Path(peer) / "app").read_text(), "new uncommitted work\n")

    def test_prepared_hook_rechecks_new_worktree_occupancy(self):
        self.fixture()
        with tempfile.TemporaryDirectory(prefix="pr-peer-hook-", dir=self.parent) as peer:
            self.git("worktree", "add", "--detach", peer, self.source)
            self.write_reference_hook(
                "import os, subprocess, sys\n"
                "payload = sys.stdin.read()\n"
                f"if sys.argv[1] == 'prepared' and ' refs/heads/{self.work}\\n' in payload:\n"
                "    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}\n"
                f"    subprocess.run(['git', '-C', {peer!r}, '-c', 'core.hooksPath=/dev/null', "
                f"'symbolic-ref', 'HEAD', 'refs/heads/{self.work}'], env=env, check=True)\n"
            )
            with self.assertRaises(finisher.FinishError):
                self.finish()
            self.assertEqual(self.git("rev-parse", self.work), self.source)
            self.assertEqual(
                finisher.git(peer, "branch", "--show-current").stdout.strip(), self.work
            )
            self.assertEqual(finisher.git(peer, "rev-parse", "HEAD").stdout.strip(), self.source)

    def test_source_change_to_an_already_merged_commit_is_rejected(self):
        self.fixture()
        real_git = finisher.git

        def race(repo, *arguments, **kwargs):
            if arguments[-4:] == ("branch", "-d", "--", self.work):
                real_git(repo, "update-ref", f"refs/heads/{self.work}", self.original_sha)
            return real_git(repo, *arguments, **kwargs)

        with patch.object(finisher, "git", side_effect=race):
            with self.assertRaises(finisher.FinishError):
                self.finish()
        self.assertEqual(self.git("rev-parse", self.work), self.original_sha)

    def test_recreated_branch_after_delete_before_checkpoint_is_preserved(self):
        self.fixture()
        self.interrupt_checkpoint("complete")
        self.git("branch", self.work, self.source)
        self.git("config", f"branch.{self.work}.description", "new task")
        with self.assertRaisesRegex(finisher.FinishError, "recreated"):
            self.finish()
        self.assertEqual(self.git("rev-parse", self.work), self.source)
        self.assertEqual(self.git("config", "--get", f"branch.{self.work}.description"), "new task")

    def test_missing_receipt_after_delete_does_not_allow_recreated_branch_deletion(self):
        self.fixture()
        self.interrupt_checkpoint("complete")
        state = json.loads(self.path.read_text())
        (self.path.parent / f"deleted-{state['delete_token']}.json").unlink()
        self.git("branch", self.work, self.source)
        with self.assertRaisesRegex(finisher.FinishError, "ambiguous"):
            self.finish()
        self.assertEqual(self.git("rev-parse", self.work), self.source)

    def test_missing_receipt_with_absent_branch_can_finish(self):
        self.fixture()
        self.interrupt_checkpoint("complete")
        state = json.loads(self.path.read_text())
        (self.path.parent / f"deleted-{state['delete_token']}.json").unlink()
        self.finish()
        self.assert_complete(self.merged)

    def test_delete_attempt_survives_sync_and_preserves_recreated_branch(self):
        self.fixture()
        self.interrupt_checkpoint("complete")
        state = json.loads(self.path.read_text())
        (self.path.parent / f"deleted-{state['delete_token']}.json").unlink()
        tree = self.git("rev-parse", f"{self.merged}^{{tree}}")
        newer = self.git("commit-tree", tree, "-p", self.merged, "-m", "upstream advanced")
        self.git("update-ref", "refs/remotes/origin/main", newer)
        real_git = finisher.git

        def recreate_during_sync(repo, *arguments, **kwargs):
            result = real_git(repo, *arguments, **kwargs)
            if arguments == ("merge", "--ff-only", newer):
                real_git(repo, "branch", self.work, self.source)
                real_git(repo, "config", f"branch.{self.work}.description", "new task")
            return result

        with patch.object(finisher, "git", side_effect=recreate_during_sync):
            with self.assertRaisesRegex(finisher.FinishError, "ambiguous"):
                self.finish()
        self.assertEqual(self.git("rev-parse", self.work), self.source)
        self.assertEqual(self.git("config", "--get", f"branch.{self.work}.description"), "new task")
        self.assertEqual(self.git("rev-parse", self.original), newer)
        self.assertTrue(json.loads(self.path.read_text())["delete_dispatched"])

    def interrupted_feature_sync_intent(self):
        self.fixture("feature")
        tree = self.git("rev-parse", f"{self.original_sha}^{{tree}}")
        stale = self.git("commit-tree", tree, "-p", self.original_sha, "-m", "old upstream")
        self.git("update-ref", "refs/remotes/origin/feature", stale)
        save = finisher.save_state

        def crash_after_intent(path, state):
            save(path, state)
            if state["phase"] == "syncing":
                raise OSError("interrupted before sync Git operation")

        with patch.object(finisher, "save_state", side_effect=crash_after_intent):
            with self.assertRaises(OSError):
                self.finish()
        return stale

    def test_diverged_upstream_on_resume_does_not_move_return_branch(self):
        self.interrupted_feature_sync_intent()
        tree = self.git("rev-parse", f"{self.base}^{{tree}}")
        divergent = self.git("commit-tree", tree, "-p", self.base, "-m", "divergent upstream")
        self.git("update-ref", "refs/remotes/origin/feature", divergent)
        journal = self.path.read_bytes()
        with self.assertRaisesRegex(finisher.FinishError, "diverged"):
            self.finish()
        self.assertEqual(self.git("rev-parse", "feature"), self.original_sha)
        self.assertEqual(self.git("branch", "--show-current"), self.work)
        self.assertEqual(self.path.read_bytes(), journal)

    def test_resume_replans_instead_of_using_stale_upstream(self):
        stale = self.interrupted_feature_sync_intent()
        self.git("update-ref", "refs/remotes/origin/feature", self.base)
        self.assertEqual(self.finish()["sync_mode"], "ahead")
        self.assertNotEqual(self.git("rev-parse", "feature"), stale)
        self.assert_complete(self.original_sha)

    def test_repository_reference_hook_is_preserved(self):
        self.fixture()
        log = self.repo / ".git" / "original-hook-events"
        self.write_reference_hook(
            "from pathlib import Path\nimport sys\n"
            "payload = sys.stdin.read()\n"
            f"if ' refs/heads/{self.work}\\n' in payload:\n"
            f"    with Path({str(log)!r}).open('a') as f: f.write(sys.argv[1] + '\\n')\n"
        )
        self.finish()
        self.assertIn("prepared", log.read_text().splitlines())
        self.assertIn("committed", log.read_text().splitlines())
        self.assert_complete(self.merged)

    def test_repository_reference_hook_can_still_reject_deletion(self):
        self.fixture()
        self.write_reference_hook(
            "import sys\npayload = sys.stdin.read()\n"
            f"if sys.argv[1] == 'prepared' and ' refs/heads/{self.work}\\n' in payload:\n"
            "    raise SystemExit(1)\n"
        )
        with self.assertRaises(finisher.FinishError):
            self.finish()
        self.assertEqual(self.git("rev-parse", self.work), self.source)

    def test_changed_private_verification_worktree_is_not_forced_removed(self):
        self.fixture()
        native_delete = finisher.native_delete

        def change_after_delete(repo, path, state, context):
            native_delete(repo, path, state, context)
            verification = finisher.verification_path(path, state["delete_token"])
            (verification / "app").write_text("unexpected private work\n")

        with patch.object(finisher, "native_delete", side_effect=change_after_delete):
            with self.assertRaisesRegex(finisher.FinishError, "has changes"):
                self.finish()
        state = json.loads(self.path.read_text())
        verification = finisher.verification_path(self.path, state["delete_token"])
        self.assertEqual((verification / "app").read_text(), "unexpected private work\n")
        self.assertEqual(state["phase"], "cleaning")

    def test_resume_can_fast_forward_new_upstream_progress(self):
        self.fixture()
        self.interrupt_checkpoint("cleaning")
        tree = self.git("rev-parse", f"{self.merged}^{{tree}}")
        newer = self.git("commit-tree", tree, "-p", self.merged, "-m", "new upstream commit")
        self.git("update-ref", "refs/remotes/origin/main", newer)
        self.finish()
        self.assert_complete(newer)

    def test_feature_can_fast_forward_its_own_upstream_before_cleanup(self):
        self.fixture("feature")
        tree = self.git("rev-parse", f"{self.original_sha}^{{tree}}")
        newer = self.git(
            "commit-tree", tree, "-p", self.original_sha, "-m", "feature upstream update"
        )
        self.git("update-ref", "refs/remotes/origin/feature", newer)
        self.finish()
        self.assert_complete(newer)

    def test_branch_used_by_another_worktree_is_preserved(self):
        self.fixture()
        self.git("switch", self.original)
        with tempfile.TemporaryDirectory(prefix="pr-peer-test-", dir=self.parent) as peer:
            self.git("worktree", "add", peer, self.work)
            with self.assertRaisesRegex(finisher.FinishError, "another worktree"):
                self.finish()
            self.assertEqual(self.git("rev-parse", self.work), self.source)
            self.assertEqual(json.loads(self.path.read_text())["phase"], "pending")

    def test_cli_entry_and_repeated_invocation(self):
        self.fixture()
        script = Path(__file__).resolve().parents[1] / "scripts" / "finish_pr.py"
        for expected_cleanup in ("deleted", "already_complete"):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(script),
                    "--repo",
                    str(self.repo),
                    "--state",
                    str(self.path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["cleanup"], expected_cleanup)
        self.assert_complete(self.merged)


if __name__ == "__main__":
    unittest.main()
