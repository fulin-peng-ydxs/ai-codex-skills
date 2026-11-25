"""Behavioral GitHub fixtures cover outcomes, CI identities and one resumable deadline."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('watch_pr', SCRIPTS / 'watch_pr.py')
watcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watcher)
HEAD, MERGE = 'a' * 40, 'b' * 40
PR_URL = 'https://github.com/example/project/pull/1'


def snapshot(**changes):
    return {'url': PR_URL, 'state': 'OPEN', 'headRefOid': HEAD, 'headRefName': 'codex/task',
            'baseRefName': 'main', 'isDraft': False, 'mergeable': 'MERGEABLE',
            'reviewDecision': '', **changes}


def merged(**changes):
    return snapshot(**{'state': 'MERGED', 'mergeCommit': {'oid': MERGE},
                       'mergedAt': '2026-11-25T10:00:00Z', **changes})


def check(bucket='pass', run=1, name='gate'):
    return {'name': name, 'bucket': bucket,
            'link': f'https://github.com/example/project/actions/runs/{run}/job/{run}0'}


def frame(pr=None, checks=None, required=None, **extra):
    checks = [check()] if checks is None else checks
    return {'pr': snapshot() if pr is None else pr, 'checks': checks,
            'required': checks if required is None else required, **extra}


class FakeClock:
    def __init__(self, elapsed=0):
        self.elapsed, self.sleeps = elapsed, []

    def now(self):
        return self.elapsed

    def wall(self):
        return 1000 + self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


class GitHub:
    def __init__(self, frames):
        self.frames, self.index, self.calls, self.current = frames, 0, [], None

    def query(self, arguments, timeout):
        self.calls.append((arguments, timeout))
        if arguments[:2] == ['pr', 'view']:
            self.current = self.frames[min(self.index, len(self.frames) - 1)]
            self.index += 1
            if isinstance(self.current, Exception):
                raise self.current
            return self.current['pr']
        data = self.current
        if data.get('metadata_error'):
            raise data['metadata_error']
        if arguments[:2] == ['pr', 'checks']:
            return data['required' if '--required' in arguments else 'checks']
        path = arguments[1]
        if '/check-runs?' in path:
            rows = [{'id': i + 1, 'name': row['name'], 'details_url': row['link'],
                     'head_sha': data.get('check_sha', HEAD), 'app': {'id': 15368},
                     'status': 'in_progress' if row['bucket'] == 'pending' else 'completed',
                     'conclusion': data.get('check_conclusion', {
                         'pass': 'success', 'fail': 'failure', 'cancel': 'cancelled',
                         'skipping': 'skipped', 'pending': None}[row['bucket']])}
                    for i, row in enumerate(data['checks'])]
            return [{'check_runs': rows}]
        if '/attempts/' in path:
            run = int(path.split('/runs/')[1].split('/')[0])
            return [{'jobs': data.get('jobs', [{'id': run * 10, 'name': 'backend',
                     'status': 'in_progress', 'steps': [
                         {'name': 'Run registered suite', 'status': 'in_progress'}]}])}]
        if '/actions/runs/' in path:
            run = int(path.rsplit('/', 1)[1])
            rows = [row for row in data['checks'] if f'/runs/{run}/' in row['link']]
            pending = any(row['bucket'] == 'pending' for row in rows)
            failed = any(row['bucket'] in {'fail', 'cancel'} for row in rows)
            return {'id': run, 'head_sha': data.get('run_sha', HEAD),
                    'run_attempt': data.get('attempt', 1),
                    'event': 'push' if run == 1 else 'pull_request',
                    'head_branch': 'codex/task',
                    'status': 'in_progress' if pending else 'completed',
                    'conclusion': None if pending else 'failure' if failed else 'success'}
        if path.endswith('/status'):
            return {'sha': HEAD, 'statuses': data.get('statuses', [])}
        raise AssertionError(arguments)


class WatchTests(unittest.TestCase):
    def run_watch(self, frames, *, timeout=1800, clock=None, **options):
        github, clock = GitHub(frames), clock or FakeClock()
        code, result = watcher.watch_pr(
            PR_URL, HEAD, timeout, query=github.query, now=clock.now, wall=clock.wall,
            sleep=clock.sleep, **options,
        )
        return code, result, clock, github.calls

    def test_only_actual_merge_allows_local_cleanup(self):
        code, result, clock, _ = self.run_watch([frame(), frame(merged())])
        self.assertEqual((code, result['status'], result['merge_sha']), (0, 'merged', MERGE))
        self.assertTrue(result['cleanup_allowed'])
        self.assertTrue(result['acceptance_complete'])
        self.assertEqual(clock.sleeps, [60])

    def test_no_reported_checks_are_not_called_successful_checks(self):
        code, result, clock, _ = self.run_watch([frame(checks=[])], timeout=65)
        self.assertEqual((code, result['status']), (8, 'timeout'))
        self.assertEqual(result['validation_status'], 'not_reported')
        self.assertEqual(clock.sleeps, [60, 5])

    def test_merged_with_running_extra_check_is_reported_separately(self):
        gate, extra = check(), check('pending', 2, 'browser')
        code, result, _, _ = self.run_watch([frame(merged(), [gate, extra], [gate])])
        self.assertEqual(code, 0)
        self.assertEqual(result['required_checks_status'], 'passed')
        self.assertEqual(result['additional_checks_status'], 'pending')
        self.assertEqual(result['pending_checks'][0]['run_id'], 2)

    def test_validation_goal_waits_after_merge_until_all_scoped_checks_finish(self):
        gate, extra = check(), check('pending', 2, 'browser')
        code, result, clock, _ = self.run_watch([
            frame(merged(), [gate, extra], [gate]),
            frame(merged(), [gate, check('pass', 2, 'browser')], [gate]),
        ], scope='all', completion='validation')
        self.assertEqual(code, 0)
        self.assertTrue(result['acceptance_complete'])
        self.assertEqual(clock.sleeps, [60])

    def test_failure_after_merge_does_not_erase_merge_proof(self):
        for bucket in ('fail', 'cancel', 'skipping'):
            with self.subTest(bucket=bucket):
                code, result, _, _ = self.run_watch(
                    [frame(merged(), [check(bucket)])], completion='validation')
                self.assertEqual((code, result['status']), (1, 'validation_failed'))
                self.assertEqual(result['merge_status'], 'merged')
                self.assertTrue(result['cleanup_allowed'])
                self.assertFalse(result['acceptance_complete'])

    def test_timeout_after_merge_retains_proof_and_pending_validation(self):
        code, result, _, _ = self.run_watch(
            [frame(merged(), [check('pending')])], timeout=10, completion='validation')
        self.assertEqual((code, result['status']), (8, 'timeout'))
        self.assertEqual(result['merge_sha'], MERGE)
        self.assertEqual(result['validation_status'], 'pending')

    def test_failed_required_check_stops_before_redundant_rerun_or_wait(self):
        for bucket in ('fail', 'cancel'):
            code, result, clock, _ = self.run_watch([frame(checks=[check(bucket)])])
            self.assertEqual((code, result['status']), (1, 'checks_failed'))
            self.assertFalse(clock.sleeps)
            self.assertEqual(result['failed_checks'][0]['run_id'], 1)
            self.assertEqual(result['rerun_guidance'], 'verify_event_sha_attempt_and_failure_stage')

    def test_duplicate_names_keep_event_run_attempt_and_failed_identity(self):
        rows = [check('fail', 1), check('pass', 2)]
        code, result, _, _ = self.run_watch([frame(checks=rows, attempt=3)])
        self.assertEqual(code, 1)
        self.assertEqual(result['ambiguous_check_names'], ['gate'])
        self.assertEqual(result['failed_checks'][0]['event'], 'push')
        self.assertEqual(result['failed_checks'][0]['attempt'], 3)
        self.assertEqual(result['failed_checks'][0]['head_sha'], HEAD)
        self.assertEqual({run['event'] for run in result['runs']}, {'push', 'pull_request'})

    def test_shared_dashboard_does_not_replace_security_failure_with_lint_success(self):
        rows = [dict(check('fail', name='security'), link='https://ci.example.test/dashboard'),
                dict(check('pass', name='lint'), link='https://ci.example.test/dashboard')]
        code, result, _, _ = self.run_watch([frame(checks=rows)])
        self.assertEqual((code, result['validation_status']), (1, 'failed'))
        self.assertEqual(result['failed_checks'][0]['name'], 'security')
        self.assertEqual(result['failed_checks'][0]['check_id'], 1)

    def test_ambiguous_same_name_dashboard_is_unverified_instead_of_selecting_one_app(self):
        row = dict(check(), link='https://ci.example.test/dashboard')
        code, result, _, _ = self.run_watch([frame(merged(), [row, row])])
        self.assertEqual(code, 0)
        self.assertEqual(result['validation_status'], 'unverified')
        self.assertFalse(result['acceptance_complete'])

    def test_cached_cli_success_cannot_hide_fresh_check_failure(self):
        code, result, _, _ = self.run_watch([frame(check_conclusion='failure')])
        self.assertEqual((code, result['validation_status']), (1, 'failed'))
        self.assertEqual(result['failed_checks'][0]['reported_bucket'], 'pass')

    def test_required_and_additional_success_each_require_verified_identity(self):
        gate, extra = check(), check(run=2, name='browser')
        for ambiguous in ('required', 'additional'):
            for scope in ('required', 'all'):
                with self.subTest(ambiguous=ambiguous, scope=scope):
                    rows = [gate, gate, extra] if ambiguous == 'required' else [gate, extra, extra]
                    code, result, _, _ = self.run_watch(
                        [frame(merged(), rows, [gate])], scope=scope)
                    self.assertEqual(code, 0)
                    self.assertEqual(result['required_checks_status'],
                                     'unverified' if ambiguous == 'required' else 'passed')
                    self.assertEqual(result['additional_checks_status'],
                                     'unverified' if ambiguous == 'additional' else 'passed')
                    selected_verified = ambiguous == 'additional' and scope == 'required'
                    self.assertEqual(result['validation_status'],
                                     'passed' if selected_verified else 'unverified')
                    self.assertEqual(result['acceptance_complete'], selected_verified)

    def test_ambiguous_failure_remains_failed_in_each_check_group(self):
        gate, extra = check(), check('fail', 2, 'browser')
        for required in ([gate], [gate, extra]):
            with self.subTest(required=required):
                _, result, _, _ = self.run_watch(
                    [frame(merged(), [gate, extra, extra], required)], scope='all')
                self.assertEqual(result['validation_status'], 'failed')
                self.assertEqual(result['required_checks_status'],
                                 'failed' if extra in required else 'passed')
                self.assertEqual(result['additional_checks_status'],
                                 'not_reported' if extra in required else 'failed')

    def test_old_attempt_is_not_relabelled_with_the_current_attempt_number(self):
        code, result, _, _ = self.run_watch([frame(
            checks=[check('fail')], attempt=2,
            jobs=[{'id': 99, 'name': 'new attempt', 'conclusion': 'success'}])])
        self.assertEqual(code, 1)
        self.assertIsNone(result['failed_checks'][0]['attempt'])
        self.assertEqual(result['failed_checks'][0]['attempt_note'], 'check_is_not_in_current_run_attempt')

    def test_commit_status_without_a_check_run_uses_its_own_source_and_state(self):
        external = {'name': 'external', 'bucket': 'pass', 'link': 'https://ci.example.test/build'}
        github = GitHub([frame(checks=[external])])
        original = github.query
        def query(arguments, timeout):
            if arguments[0] == 'api' and '/check-runs?' in arguments[1]:
                return [{'check_runs': []}]
            if arguments[0] == 'api' and arguments[1].endswith('/status'):
                return {'sha': HEAD, 'statuses': [{
                    'context': 'external', 'target_url': external['link'], 'state': 'pending',
                }]}
            return original(arguments, timeout)
        clock = FakeClock()
        code, result = watcher.watch_pr(PR_URL, HEAD, 5, query=query, now=clock.now,
                                         wall=clock.wall, sleep=clock.sleep)
        self.assertEqual((code, result['validation_status']), (8, 'pending'))

    def test_verified_repair_updates_source_but_keeps_original_branch_protection(self):
        new_head, original_sha = 'c' * 40, 'd' * 40
        state = {'version': 1, 'phase': 'preparing', 'context': {
            'pr_url': PR_URL, 'source_sha': HEAD, 'return_sha': original_sha,
            'return_branch': 'main', 'allowed_commits': [HEAD, new_head],
        }}
        self.run_watch([frame(checks=[check('fail')])], state=state)
        github, clock = GitHub([frame(merged(headRefOid=new_head),
                                       check_sha=new_head, run_sha=new_head)]), FakeClock(20)
        code, _ = watcher.watch_pr(PR_URL, new_head, new_round=True, state=state,
                                    query=github.query, now=clock.now, wall=clock.wall,
                                    sleep=clock.sleep)
        self.assertEqual(code, 0)
        self.assertEqual(state['context']['source_sha'], new_head)
        self.assertEqual(state['context']['return_sha'], original_sha)
        self.assertEqual(state['watch']['remaining_seconds'], 1780)

    def test_empty_or_mismatched_reviewed_commit_list_cannot_admit_a_source(self):
        for allowed in ([], ['c' * 40]):
            state = {'context': {'pr_url': PR_URL, 'source_sha': HEAD, 'allowed_commits': allowed}}
            with self.assertRaisesRegex(ValueError, 'reviewed commit list'):
                self.run_watch([frame(merged())], state=state)

    def test_rejected_retarget_does_not_mutate_saved_source_round(self):
        state = {'context': {'pr_url': PR_URL, 'source_sha': HEAD}}
        self.run_watch([frame(snapshot(reviewDecision='REVIEW_REQUIRED'))], state=state)
        before = json.loads(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'target branch changed'):
            watcher.watch_pr(PR_URL, 'c' * 40, state=state, expected_base='release', new_round=True)
        self.assertEqual(state, before)

    def test_review_required_is_an_external_action_without_waiting_thirty_minutes(self):
        code, result, clock, _ = self.run_watch([frame(snapshot(reviewDecision='REVIEW_REQUIRED'))])
        self.assertEqual((code, result['status']), (3, 'review_required'))
        self.assertFalse(clock.sleeps)
        code, result, _, _ = self.run_watch([
            frame(snapshot(reviewDecision='REVIEW_REQUIRED')), frame(merged()),
        ], wait_for_review=True)
        self.assertEqual((code, result['status']), (0, 'merged'))

    def test_changed_head_or_base_never_allows_cleanup(self):
        for data, options, reason in (
            (merged(headRefOid='c' * 40), {}, 'head_changed'),
            (merged(baseRefName='release'), {'expected_base': 'main'}, 'target_changed'),
        ):
            code, result, _, _ = self.run_watch([frame(data)], **options)
            self.assertEqual((code, result['status']), (1, reason))
            self.assertFalse(result['cleanup_allowed'])

    def test_closed_conflict_draft_and_rejected_review_stop_early(self):
        for changes, status in (({'state': 'CLOSED'}, 'closed_unmerged'),
                                ({'mergeable': 'CONFLICTING'}, 'conflict'),
                                ({'isDraft': True}, 'draft'),
                                ({'reviewDecision': 'CHANGES_REQUESTED'}, 'changes_requested')):
            code, result, _, _ = self.run_watch([frame(snapshot(**changes))])
            self.assertEqual((code, result['status']), (1, status))

    def test_invalid_merge_proof_and_three_network_errors_are_not_success(self):
        for data in ([frame(merged(mergeCommit=None))], [watcher.QueryFailure('network')]):
            code, result, clock, _ = self.run_watch(data)
            self.assertEqual((code, result['status']), (2, 'query_error'))
            self.assertEqual(clock.elapsed, 120)

    def test_source_mismatch_in_check_or_run_does_not_validate_success(self):
        for changes in ({'check_sha': 'c' * 40}, {'run_sha': 'c' * 40}):
            code, result, _, _ = self.run_watch([frame(**changes)])
            self.assertEqual((code, result['status']), (2, 'query_error'))

    def test_ci_query_failure_does_not_hide_an_already_verified_merge(self):
        code, result, _, _ = self.run_watch([
            frame(merged(), metadata_error=watcher.QueryFailure('network'))])
        self.assertEqual(code, 0)
        self.assertTrue(result['cleanup_allowed'])
        self.assertFalse(result['acceptance_complete'])
        self.assertEqual(result['validation_status'], 'unverified')

    def test_validation_stops_after_three_ci_query_failures_and_keeps_merge_proof(self):
        code, result, clock, _ = self.run_watch([
            frame(merged(), metadata_error=watcher.QueryFailure('network')),
        ], completion='validation')
        self.assertEqual((code, result['status']), (2, 'query_error'))
        self.assertEqual(result['merge_sha'], MERGE)
        self.assertTrue(result['cleanup_allowed'])
        self.assertFalse(result['acceptance_complete'])
        self.assertEqual(clock.elapsed, 120)

    def test_remaining_budget_limits_every_network_command(self):
        code, result, _, calls = self.run_watch([frame(checks=[])], timeout=5)
        self.assertEqual((code, result['elapsed_seconds']), (8, 5))
        self.assertTrue(all(timeout == 5 for _, timeout in calls))

    def test_progress_is_only_emitted_for_state_changes(self):
        output = []
        self.run_watch([frame(checks=[check('pending')])], timeout=125, emit=output.append)
        self.assertEqual(len(output), 1)

    def test_default_monitor_does_not_print_snapshots(self):
        with patch('builtins.print') as output:
            _, result, clock, _ = self.run_watch([frame(checks=[])])
        self.assertEqual((result['polls'], clock.elapsed), (30, 1800))
        output.assert_not_called()

    def test_saved_budget_survives_resume_without_new_authorization(self):
        state, clock = {}, FakeClock()
        self.run_watch([frame(snapshot(reviewDecision='REVIEW_REQUIRED'))], state=state, clock=clock)
        clock.elapsed = 50
        _, result, _, calls = self.run_watch([frame(checks=[])], timeout=5000,
                                            state=state, clock=clock)
        self.assertEqual(result['elapsed_seconds'], 1750)
        self.assertEqual(state['watch']['budget_seconds'], 1800)
        self.assertTrue(all(timeout <= 30 for _, timeout in calls))

    def test_resume_cannot_silently_drop_failed_browser_scope_or_validation_goal(self):
        gate, extra = check(), check('fail', 2, 'browser')
        state = {}
        code, _, _, _ = self.run_watch([frame(merged(), [gate, extra], [gate])],
                                      state=state, scope='all', completion='validation')
        self.assertEqual(code, 1)
        for options in ({'completion': 'validation'}, {'scope': 'all', 'completion': 'merge'}):
            with self.assertRaisesRegex(ValueError, 'explicit user goal change'):
                self.run_watch([frame(merged(), [gate, extra], [gate])], state=state, **options)
        code, result, _, _ = self.run_watch(
            [frame(merged(), [gate, extra], [gate])], state=state,
            completion='validation', allow_goal_change=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['verification_scope']['checks'], 'required')
        self.assertEqual(result['additional_checks_status'], 'failed')
        self.assertEqual(len(state['goal_changes']), 1)

    def test_dropping_tracked_run_preserves_failed_evidence_across_saved_resume(self):
        github, clock, state = GitHub([frame(merged())]), FakeClock(), {}
        original_query = github.query

        def query(arguments, timeout):
            result = original_query(arguments, timeout)
            if arguments[0] == 'api' and arguments[1].endswith('/actions/runs/9'):
                return {**result, 'conclusion': 'failure', 'run_attempt': 3}
            return result

        with tempfile.TemporaryDirectory(prefix='git-push-evidence-') as directory:
            path = Path(directory) / 'state.json'
            code, result = watcher.watch_pr(
                PR_URL, HEAD, 1800, query=query, now=clock.now, wall=clock.wall,
                sleep=clock.sleep, state=state, state_path=path, run_ids=(9,),
                completion='validation')
            self.assertEqual((code, result['validation_status']), (1, 'failed'))
            previous_result = json.loads(path.read_text())['watch']['latest']
            state = json.loads(path.read_text())
            code, result, _, _ = self.run_watch(
                [frame(merged())], state=state, state_path=path,
                completion='validation', allow_goal_change=True)
            self.assertEqual((code, result['validation_status']), (0, 'passed'))
            saved = json.loads(path.read_text())
            history = saved['goal_changes'][0]
            self.assertEqual(history['previous']['run_ids'], [9])
            self.assertEqual(history['identity'], {'url': PR_URL, 'head': HEAD})
            self.assertEqual(history['last_status'], 'validation_failed')
            self.assertEqual(history['latest'], previous_result)
            failed = next(run for run in history['latest']['runs'] if run['id'] == 9)
            self.assertEqual((failed['head_sha'], failed['run_attempt'], failed['conclusion']),
                             (HEAD, 3, 'failure'))
            # Subsequent resumes and edits to the current result cannot rewrite history.
            self.run_watch([frame(merged())], state=saved, state_path=path,
                           completion='validation')
            saved['watch']['latest']['runs'].clear()
            self.assertEqual(saved['goal_changes'][0], history)
            self.assertEqual(json.loads(path.read_text())['goal_changes'], [history])

    def test_missing_tool_stops_immediately(self):
        code, result, clock, _ = self.run_watch([FileNotFoundError()])
        self.assertEqual((code, result['reason'], clock.elapsed), (2, 'gh_not_installed', 0))


class QueryTests(unittest.TestCase):
    def test_pending_and_failed_exit_codes_preserve_json(self):
        for code, bucket in ((8, 'pending'), (1, 'fail')):
            completed = subprocess.CompletedProcess([], code, json.dumps([{'bucket': bucket}]), '')
            with patch.object(watcher.subprocess, 'run', return_value=completed):
                self.assertEqual(watcher.query_json(['pr', 'checks', PR_URL], 10), [{'bucket': bucket}])

    def test_missing_checks_and_missing_login_are_distinct(self):
        for message, empty in (('no required checks reported on the branch', True),
                               ('To get started, run gh auth login', False)):
            with patch.object(watcher.subprocess, 'run', return_value=
                              subprocess.CompletedProcess([], 1, '', message)):
                if empty:
                    self.assertEqual(watcher.query_json(['pr', 'checks', PR_URL], 1), [])
                else:
                    with self.assertRaisesRegex(watcher.QueryFailure, 'github_login_required'):
                        watcher.query_json(['api', 'user'], 1)

    def test_invalid_json_timeout_and_secrets_in_stderr_are_not_echoed(self):
        with patch.object(watcher.subprocess, 'run', return_value=
                          subprocess.CompletedProcess([], 1, '', 'private-token-value')):
            with self.assertRaises(watcher.QueryFailure) as caught:
                watcher.query_json(['api', 'user'], 1)
            self.assertNotIn('private-token-value', str(caught.exception))
        with patch.object(watcher.subprocess, 'run', side_effect=subprocess.TimeoutExpired('gh', 1)), self.assertRaisesRegex(watcher.QueryFailure, 'gh_command_timeout'):
            watcher.query_json(['api', 'user'], 1)


if __name__ == '__main__':
    unittest.main()
