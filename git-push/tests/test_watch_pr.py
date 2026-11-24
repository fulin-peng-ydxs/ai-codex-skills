"""Exercise PR outcomes and deadlines without GitHub access or repository writes."""

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "watch_pr.py"
SPEC = importlib.util.spec_from_file_location("watch_pr", MODULE_PATH)
watcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watcher)
HEAD = "a" * 40
MERGE = "b" * 40
PR_URL = "https://github.com/example/project/pull/1"


def snapshot(**changes):
    return {
        "state": "OPEN",
        "headRefOid": HEAD,
        "headRefName": "codex/task",
        "baseRefName": "main",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "",
        **changes,
    }


def merged(**changes):
    return snapshot(
        **{
            "state": "MERGED",
            "mergedAt": "2026-11-24T10:00:00Z",
            "mergeCommit": {"oid": MERGE},
            **changes,
        }
    )


class FakeClock:
    def __init__(self):
        self.elapsed = 0
        self.sleeps = []

    def now(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


class WatchTests(unittest.TestCase):
    def run_watch(self, responses, *, timeout=1800):
        responses = iter(responses)
        clock = FakeClock()
        calls = []

        def query(arguments, command_timeout):
            calls.append((arguments, command_timeout))
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return response

        code, result = watcher.watch_pr(
            PR_URL, HEAD, timeout, query=query, now=clock.now, sleep=clock.sleep
        )
        return code, result, clock, calls

    def test_merge_requires_actual_platform_evidence(self):
        code, result, clock, calls = self.run_watch(
            [snapshot(), [{"name": "gate", "bucket": "pass"}], merged()]
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["merge_sha"], MERGE)
        self.assertEqual(result["polls"], 2)
        self.assertEqual(clock.sleeps, [60])
        self.assertIn("--required", calls[1][0])

    def test_no_checks_does_not_count_as_merge(self):
        code, result, clock, _ = self.run_watch([snapshot(), []] * 2, timeout=65)
        self.assertEqual((code, result["status"]), (8, "timeout"))
        self.assertEqual(clock.sleeps, [60, 5])

    def test_default_wait_is_bounded_without_repeated_output(self):
        with patch("builtins.print") as output:
            code, result, clock, _ = self.run_watch([snapshot(), []] * 30)
        self.assertEqual((code, result["polls"], clock.elapsed), (8, 30, 1800))
        output.assert_not_called()

    def test_failed_or_cancelled_required_check_stops_early(self):
        for bucket in ("fail", "cancel"):
            with self.subTest(bucket=bucket):
                code, result, clock, _ = self.run_watch(
                    [snapshot(), [{"name": "gate", "bucket": bucket, "link": "check-link"}]]
                )
                self.assertEqual((code, result["status"]), (1, "checks_failed"))
                self.assertEqual(clock.sleeps, [])
                self.assertEqual(result["failed_checks"][0]["name"], "gate")

    def test_changed_head_never_allows_cleanup_even_when_merged(self):
        code, result, _, _ = self.run_watch([merged(headRefOid="c" * 40)])
        self.assertEqual((code, result["status"]), (1, "head_changed"))

    def test_closed_conflicted_draft_and_changes_requested_are_distinct(self):
        for fields, status in (
            ({"state": "CLOSED"}, "closed_unmerged"),
            ({"mergeable": "CONFLICTING"}, "conflict"),
            ({"isDraft": True}, "draft"),
            ({"reviewDecision": "CHANGES_REQUESTED"}, "changes_requested"),
        ):
            with self.subTest(status=status):
                code, result, _, _ = self.run_watch([snapshot(**fields)])
                self.assertEqual((code, result["status"]), (1, status))

    def test_missing_merge_evidence_is_not_success(self):
        code, result, _, _ = self.run_watch([merged(mergeCommit=None)] * 3)
        self.assertEqual((code, result["status"]), (2, "query_error"))

    def test_three_errors_stop_without_resetting_deadline(self):
        error = watcher.QueryFailure("network")
        code, result, clock, _ = self.run_watch([error] * 3)
        self.assertEqual((code, result["status"], clock.elapsed), (2, "query_error", 120))

    def test_transient_errors_can_recover(self):
        error = watcher.QueryFailure("network")
        code, result, _, _ = self.run_watch([error, snapshot(), [], error, merged()])
        self.assertEqual((code, result["status"]), (0, "merged"))

    def test_missing_tool_stops_immediately(self):
        code, result, clock, _ = self.run_watch([FileNotFoundError()])
        self.assertEqual((code, result["reason"], clock.elapsed), (2, "gh_not_installed", 0))

    def test_subprocess_timeout_uses_remaining_budget(self):
        code, result, _, calls = self.run_watch([snapshot(), []] * 2, timeout=65)
        self.assertEqual(code, 8)
        self.assertEqual([timeout for _, timeout in calls], [30, 30, 5, 5])
        self.assertEqual(result["elapsed_seconds"], 65)

    def test_unknown_response_is_not_interpreted_as_pending(self):
        for response in ({}, {"state": "OTHER"}, []):
            with self.subTest(response=response):
                code, result, _, _ = self.run_watch([response] * 3)
                self.assertEqual((code, result["status"]), (2, "query_error"))


class QueryTests(unittest.TestCase):
    def test_pending_and_failed_check_exit_codes_preserve_json(self):
        for code, bucket in ((8, "pending"), (1, "fail")):
            with self.subTest(code=code):
                completed = subprocess.CompletedProcess(
                    [], code, json.dumps([{"bucket": bucket}]), ""
                )
                with patch.object(watcher.subprocess, "run", return_value=completed) as run:
                    result = watcher.query_json(["pr", "checks", PR_URL], 10)
                self.assertEqual(result, [{"bucket": bucket}])
                self.assertEqual(run.call_args.kwargs["timeout"], 10)
                self.assertIsInstance(run.call_args.args[0], list)

    def test_no_required_checks_is_distinct_from_auth_failure(self):
        for stderr, empty_checks in (
            ("no required checks reported on the branch", True),
            ("authentication required", False),
        ):
            with self.subTest(stderr=stderr):
                completed = subprocess.CompletedProcess([], 1, "", stderr)
                with patch.object(watcher.subprocess, "run", return_value=completed):
                    if empty_checks:
                        self.assertEqual(watcher.query_json(["pr", "checks", PR_URL], 10), [])
                    else:
                        with self.assertRaises(watcher.QueryFailure):
                            watcher.query_json(["pr", "checks", PR_URL], 10)

    def test_invalid_json_and_timeout_are_query_errors(self):
        with patch.object(
            watcher.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "invalid", ""),
        ):
            with self.assertRaises(watcher.QueryFailure):
                watcher.query_json(["pr", "view", PR_URL], 1)
        with patch.object(
            watcher.subprocess, "run", side_effect=subprocess.TimeoutExpired("gh", 1)
        ):
            with self.assertRaises(watcher.QueryFailure):
                watcher.query_json(["pr", "view", PR_URL], 1)


if __name__ == "__main__":
    unittest.main()
