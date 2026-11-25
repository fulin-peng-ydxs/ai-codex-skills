"""Read-only preflight and installation-vs-test diagnostics without platform writes."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import github_pr as github


class PreflightTests(unittest.TestCase):
    def query(self, classic=None, rules=None, **repo_changes):
        calls = []
        def read(arguments):
            calls.append(arguments)
            self.assertEqual(arguments[0], 'api')
            self.assertFalse(any(arg in {'--method', '-X', '--input', '--field', '-f'} for arg in arguments))
            path = arguments[1]
            if path == 'user':
                return {'login': 'author'}
            if path.endswith('/protection'):
                if isinstance(classic, Exception):
                    raise classic
                return classic or {'required_pull_request_reviews': {'required_approving_review_count': 1}}
            if '/rules/branches/' in path:
                if isinstance(rules, Exception):
                    raise rules
                return [] if rules is None else rules
            return {'default_branch': 'main', 'permissions': {'push': True},
                    'allow_merge_commit': True, 'allow_auto_merge': True, **repo_changes}
        return read, calls

    def preflight(self, **options):
        read, calls = self.query(**options)
        result = github.preflight('owner/project', read, capabilities={'create': True, 'merge': True})
        return result, calls

    def test_classic_review_is_found_even_when_rulesets_are_empty(self):
        result, calls = self.preflight()
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['required_approvals'], 1)
        self.assertEqual(result['policies']['rulesets']['rules'], [])
        self.assertTrue(any('/protection' in call[1] for call in calls))
        self.assertTrue(any('/rules/branches/' in call[1] for call in calls))
        self.assertFalse(result['write_access_tested'])

    def test_only_explicit_unprotected_response_means_absent(self):
        for message, expected in (('Branch not protected', 'absent'), ('Not Found', 'unknown')):
            result, _ = self.preflight(classic=github.QueryFailure('http', http_status=404, api_message=message))
            self.assertEqual(result['policies']['classic']['status'], expected)

    def test_policy_permission_or_plan_limit_is_unverified_not_unprotected(self):
        result, _ = self.preflight(rules=github.QueryFailure('http', http_status=403))
        self.assertEqual(result['status'], 'needs_attention')
        self.assertEqual(result['policies']['rulesets']['status'], 'unknown')
        self.assertIsNone(result['required_approvals'])

    def test_linear_history_and_branch_merge_methods_are_not_ordinary_merge_permission(self):
        result, _ = self.preflight(classic={'required_linear_history': {'enabled': True}})
        self.assertIn('linear_history_requires_merge_decision', result['attention'])
        result, _ = self.preflight(rules=[{
            'type': 'pull_request', 'parameters': {'allowed_merge_methods': ['squash']},
        }])
        self.assertIn('branch_rule_disallows_ordinary_merge', result['attention'])

    def test_ruleset_reviews_merge_method_and_source_permissions_are_reported(self):
        result, _ = self.preflight(
            rules=[{'type': 'pull_request', 'parameters': {'required_approving_review_count': 2}}],
            allow_merge_commit=False, permissions={'push': False})
        self.assertEqual(result['required_approvals'], 2)
        self.assertIn('ordinary_merge_unavailable_or_unverified', result['attention'])
        self.assertIn('source_push_permission_unverified', result['attention'])

    def test_fork_source_permission_is_not_taken_from_read_only_target(self):
        read, _calls = self.query(permissions={'push': False})
        def source_read(arguments):
            if arguments[1] == 'repos/author/project':
                return {'permissions': {'push': True}}
            return read(arguments)
        result = github.preflight('owner/project', source_read, source='author/project',
                                  capabilities={'create': True, 'merge': True})
        self.assertTrue(result['source_can_push'])
        self.assertEqual(result['status'], 'ready')

    def test_branch_with_slash_is_encoded_without_guessing_repository(self):
        read, calls = self.query()
        github.preflight('owner/project', read, base='release/stable', capabilities={'create': True, 'merge': True})
        self.assertTrue(any('release%2Fstable' in call[1] for call in calls))
        for value in ('../repo', 'owner/../repo', '--option', 'owner/repo?token=value'):
            with self.assertRaises(ValueError):
                github.repository_name(value)

    def test_help_probes_check_real_cli_flags_and_do_not_mutate(self):
        seen = []
        def run(arguments, **options):
            seen.append(arguments)
            return subprocess.CompletedProcess(arguments, 0, '--base --head --body-file --auto --merge --match-head-commit', '')
        self.assertEqual(github.cli_capabilities(run), {'create': True, 'merge': True})
        self.assertTrue(all(call[-1] == '--help' for call in seen))
        with self.assertRaises(FileNotFoundError):
            github.cli_capabilities(lambda *_args, **_options: (_ for _ in ()).throw(FileNotFoundError()))

    def test_url_validation_rejects_credentials_queries_and_option_like_paths(self):
        for url in ('http://github.com/a/b/pull/1', 'https://token@github.com/a/b/pull/1',
                    'https://github.com/a/b/pull/1?token=secret', 'https://github.com/a/b/pull/0'):
            with self.assertRaises(ValueError):
                github.parse_pr_url(url)
        self.assertEqual(github.parse_pr_url('https://git.example.com/a/b/pull/12'),
                         ('git.example.com', 'a/b', 12))


class StepTests(unittest.TestCase):
    def test_long_dependency_install_is_not_described_as_a_running_test(self):
        result = github.job_stage({'id': 10, 'name': 'browser', 'status': 'in_progress', 'steps': [
            {'name': 'Run python -m pip install --require-hashes -r requirements.lock', 'status': 'in_progress'},
            {'name': 'Run registered suite', 'status': 'queued'},
        ]})
        self.assertEqual((result['stage'], result['test_execution']), ('dependencies', 'not_started'))

    def test_cancelled_install_with_skipped_suite_retains_both_facts(self):
        result = github.job_stage({'id': 10, 'conclusion': 'cancelled', 'status': 'completed', 'steps': [
            {'name': 'npm ci', 'status': 'completed', 'conclusion': 'cancelled'},
            {'name': 'Run registered suite', 'status': 'completed', 'conclusion': 'skipped'},
        ]})
        self.assertEqual(result['conclusion'], 'cancelled')
        self.assertEqual((result['stage'], result['test_execution']), ('dependencies', 'not_started'))

    def test_skipped_check_is_incomplete_and_empty_checks_are_not_reported(self):
        self.assertEqual(github.outcome([]), 'not_reported')
        self.assertEqual(github.outcome([{'bucket': 'skipping'}]), 'incomplete')
        self.assertEqual(github.outcome([{'bucket': 'pass'}]), 'passed')

    def test_paginated_metadata_is_combined_and_malformed_data_rejected(self):
        self.assertEqual(github.pages([{'jobs': [{'id': 1}]}, {'jobs': [{'id': 2}]}], 'jobs'),
                         [{'id': 1}, {'id': 2}])
        for value in ({}, [{'jobs': None}], [{'jobs': [False]}]):
            with self.assertRaises(github.QueryFailure):
                github.pages(value, 'jobs')

    def test_api_errors_keep_status_without_echoing_authentication_output(self):
        completed = subprocess.CompletedProcess([], 1, json.dumps({'message': 'Branch not protected'}),
                                                'gh: Branch not protected (HTTP 404) private-token')
        with patch.object(github.subprocess, 'run', return_value=completed), self.assertRaises(github.QueryFailure) as caught:
            github.query_json(['api', 'policy'], 3)
        self.assertEqual(caught.exception.http_status, 404)
        self.assertNotIn('private-token', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
