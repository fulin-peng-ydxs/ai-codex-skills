#!/usr/bin/env python3
"""Read-only GitHub preflight and CI identity/step diagnostics; never rerun or change rules."""

import argparse
import json
import re
import subprocess
from collections import Counter
from urllib.parse import quote, urlparse

SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
PR_FIELDS = (
    "url,state,mergedAt,mergeCommit,headRefOid,headRefName,baseRefName,mergeable,"
    "isDraft,reviewDecision,mergeStateStatus"
)
BUCKETS = {"pass", "fail", "pending", "skipping", "cancel"}


class QueryFailure(Exception):
    """Only a validated response can establish a platform fact."""

    def __init__(self, reason, *, http_status=None, api_message=None):
        super().__init__(reason)
        self.http_status = http_status
        self.api_message = api_message


def query_json(arguments, timeout):
    """Keep tokens, authentication output and full logs out of the returned diagnostics."""
    try:
        result = subprocess.run(
            ["gh", *arguments], capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise QueryFailure("gh_command_timeout") from error
    checks = arguments[:2] == ["pr", "checks"]
    if (checks and result.returncode == 1 and not result.stdout.strip()
            and result.stderr.lower().strip().startswith(
                ("no checks reported", "no required checks reported")
            )):
        return []
    if result.returncode and not result.stdout.strip():
        login = any(term in result.stderr.lower() for term in (
            "gh auth login", "not logged", "authentication required",
        ))
        raise QueryFailure("github_login_required" if login else "gh_request_failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise QueryFailure("invalid_gh_json") from error
    allowed = (0, 1, 8) if checks else (0,)
    if result.returncode not in allowed:
        status = re.search(r"HTTP (\d{3})", result.stderr)
        raise QueryFailure(
            "gh_request_failed", http_status=int(status[1]) if status else None,
            api_message=value.get("message") if isinstance(value, dict) else None,
        )
    return value


def repository_name(value):
    parts = value.split("/")
    if len(parts) != 2 or any(
        part in {"", ".", ".."} or not re.fullmatch(r"[\w.-]+", part, re.ASCII)
        for part in parts
    ):
        raise ValueError("repository must be OWNER/REPO")
    return value


def parse_pr_url(value):
    url = urlparse(value)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.port is not None
            or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", url.hostname)):
        raise ValueError("PR URL must be an HTTPS GitHub host URL without credentials")
    match = re.fullmatch(r"/([^/]+/[^/]+)/pull/([1-9][0-9]*)/?", url.path)
    if not match:
        raise ValueError("PR URL must identify OWNER/REPO/pull/NUMBER")
    return url.hostname, repository_name(match[1]), int(match[2])


def api(query, host, path):
    return query(["api", path, "--hostname", host])


def pages(value, key):
    documents = value if isinstance(value, list) else [value]
    if any(not isinstance(page, dict) or not isinstance(page.get(key), list) for page in documents):
        raise QueryFailure("invalid_paginated_response")
    items = [item for page in documents for item in page[key]]
    if any(not isinstance(item, dict) for item in items):
        raise QueryFailure("invalid_paginated_item")
    return items


def cli_capabilities(run=subprocess.run):
    """Help probes do not create a PR, start a login or mutate a repository."""
    supported = {}
    for action, flags in (("create", ("--base", "--head", "--body-file")),
                          ("merge", ("--auto", "--merge", "--match-head-commit"))):
        result = run(
            ["gh", "pr", action, "--help"], text=True, capture_output=True,
            timeout=30, check=False,
        )
        supported[action] = result.returncode == 0 and all(flag in result.stdout for flag in flags)
    return supported


def preflight(repository, query, *, host="github.com", base=None, source=None, capabilities=None):
    repository_name(repository)
    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host):
        raise ValueError("invalid GitHub hostname")
    source = repository_name(source or repository)
    me = api(query, host, "user")
    target = api(query, host, f"repos/{repository}")
    if not isinstance(me, dict) or not me.get("login") or not isinstance(target, dict):
        raise QueryFailure("invalid_account_or_repository")
    base = base or target.get("default_branch")
    if not isinstance(base, str) or not base:
        raise QueryFailure("missing_target_branch")
    source_data = target if source == repository else api(query, host, f"repos/{source}")
    policies = {}
    paths = {
        "classic": f"repos/{repository}/branches/{quote(base, safe='')}/protection",
        "rulesets": f"repos/{repository}/rules/branches/{quote(base, safe='')}",
    }
    for kind, path in paths.items():
        try:
            value = api(query, host, path)
            if not isinstance(value, dict if kind == "classic" else list):
                raise QueryFailure("invalid_branch_policy")
            policies[kind] = {"status": "available", "rules": value}
        except QueryFailure as error:
            absent = (kind == "classic" and error.http_status == 404
                      and error.api_message == "Branch not protected")
            policies[kind] = {"status": "absent" if absent else "unknown"}
    permissions = source_data.get("permissions") if isinstance(source_data, dict) else None
    permissions = permissions if isinstance(permissions, dict) else {}
    capabilities = capabilities or {}
    attention = []
    if permissions.get("push") is not True:
        attention.append("source_push_permission_unverified")
    if target.get("allow_merge_commit") is not True:
        attention.append("ordinary_merge_unavailable_or_unverified")
    if target.get("allow_auto_merge") is not True:
        attention.append("auto_merge_unavailable_or_unverified")
    if any(policy["status"] == "unknown" for policy in policies.values()):
        attention.append("branch_policy_incomplete")
    if not all(capabilities.get(action) is True for action in ("create", "merge")):
        attention.append("cli_capability_unverified")
    classic = policies["classic"].get("rules", {})
    reviews = classic.get("required_pull_request_reviews") or {}
    rules = policies["rulesets"].get("rules", [])
    if ((classic.get("required_linear_history") or {}).get("enabled") is True
            or any(rule.get("type") == "required_linear_history" for rule in rules)):
        attention.append("linear_history_requires_merge_decision")
    if any(rule.get("type") == "pull_request"
           and isinstance((rule.get("parameters") or {}).get("allowed_merge_methods"), list)
           and "merge" not in rule["parameters"]["allowed_merge_methods"] for rule in rules):
        attention.append("branch_rule_disallows_ordinary_merge")
    approvals = [reviews.get("required_approving_review_count", 0)] + [
        (rule.get("parameters") or {}).get("required_approving_review_count", 0)
        for rule in rules if rule.get("type") == "pull_request"
    ]
    if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in approvals):
        raise QueryFailure("invalid_approval_count")
    return {
        "status": "ready" if not attention else "needs_attention", "login": me["login"],
        "repository": repository, "source_repository": source, "base_branch": base,
        "capabilities": capabilities, "source_can_push": permissions.get("push"),
        "ordinary_merge_allowed": target.get("allow_merge_commit"),
        "auto_merge_allowed": target.get("allow_auto_merge"), "policies": policies,
        "required_approvals": None if any(policy["status"] == "unknown" for policy in policies.values())
        else max(approvals), "known_approval_lower_bound": max(approvals), "attention": attention,
        "write_access_tested": False,
    }


def check_rows(value):
    if not isinstance(value, list) or any(
        not isinstance(item, dict) or item.get("bucket") not in BUCKETS
        or not isinstance(item.get("name"), str) for item in value
    ):
        raise QueryFailure("invalid_checks")
    return value


def outcome(checks):
    if not checks:
        return "not_reported"
    if any(item["bucket"] in {"fail", "cancel"} for item in checks):
        return "failed"
    if any(item["bucket"] == "pending" for item in checks):
        return "pending"
    # skipped is observable, but does not prove that the check executed.
    if any(item["bucket"] == "skipping" for item in checks):
        return "incomplete"
    return "passed"


def check_bucket(row):
    """Fresh check-run evidence wins over a cached CLI rollup, without assuming success."""
    if row.get("status") in {"queued", "in_progress", "waiting", "pending", "requested"}:
        return "pending"
    if row.get("status") != "completed":
        raise QueryFailure("invalid_check_run_status")
    conclusion = row.get("conclusion")
    if conclusion == "success":
        return "pass"
    if conclusion == "cancelled":
        return "cancel"
    if conclusion in {"skipped", "neutral"}:
        return "skipping"
    if conclusion in {"failure", "timed_out", "action_required", "startup_failure", "stale"}:
        return "fail"
    raise QueryFailure("invalid_check_run_conclusion")


def job_stage(job):
    """A running install is not described as a running test suite."""
    steps = job.get("steps", [])
    active = next((step for step in steps if step.get("status") == "in_progress"), None)
    if active is None:
        active = next((step for step in steps if step.get("conclusion") in {"failure", "cancelled"}), {})
    name = active.get("name", "")
    lower = name.lower()
    stage = "unknown"
    if any(word in lower for word in ("install", "pip ", "npm ci", "dependency")):
        stage = "dependencies"
    elif any(word in lower for word in ("reconcile", "summary", "aggregate", "receipt")):
        stage = "aggregation"
    elif any(word in lower for word in ("test", "registered suite", "pytest", "vitest", "playwright")):
        stage = "execution"
    elif name:
        stage = "preparation"
    execution = [step for step in steps if any(
        term in step.get("name", "").lower()
        for term in ("registered suite", "pytest", "vitest", "playwright test")
    )]
    executed = "unknown" if not execution else (
        "not_started" if all(step.get("conclusion") == "skipped" for step in execution)
        else "started" if any(step.get("status") in {"in_progress", "completed"}
                              and step.get("conclusion") != "skipped" for step in execution)
        else "not_started"
    )
    return {
        "job_id": job.get("id"), "name": job.get("name"), "status": job.get("status"),
        "conclusion": job.get("conclusion"), "stage": stage, "active_step": name,
        "step_started_at": active.get("started_at"), "test_execution": executed,
    }


def checks_snapshot(pr_url, head, query, *, run_ids=(), diagnose=True):
    """Keep same-name events/attempts separate; never treat a new run as replacing an old one."""
    host, repository, _ = parse_pr_url(pr_url)
    required = check_rows(query(["pr", "checks", pr_url, "--required", "--json", "name,bucket,link"]))
    all_checks = check_rows(query(["pr", "checks", pr_url, "--json", "name,bucket,link"]))
    required_keys = {(item["name"], item.get("link")) for item in required}
    checks = [dict(item, required=(item["name"], item.get("link")) in required_keys)
              for item in all_checks]
    for item in required:
        if not any((row["name"], row.get("link")) == (item["name"], item.get("link")) for row in checks):
            checks.append(dict(item, required=True))
    runs = {}
    if diagnose and (checks or run_ids):
        raw = query([
            "api", f"repos/{repository}/commits/{head}/check-runs?filter=all&per_page=100",
            "--hostname", host, "--paginate", "--slurp",
        ])
        indexed = {}
        for row in pages(raw, "check_runs"):
            indexed.setdefault((row.get("details_url"), row.get("name")), []).append(row)
        unmatched = [item for item in checks if (item.get("link"), item["name"]) not in indexed]
        statuses = []
        if unmatched:
            status = api(query, host, f"repos/{repository}/commits/{head}/status")
            if not isinstance(status, dict) or status.get("sha") != head:
                raise QueryFailure("status_source_sha_mismatch")
            statuses = status.get("statuses", [])
            if not isinstance(statuses, list) or any(not isinstance(row, dict) for row in statuses):
                raise QueryFailure("invalid_commit_statuses")
        for item in checks:
            candidates = indexed.get((item.get("link"), item["name"]), [])
            # Shared external dashboards, apps or repeated check names are not a
            # unique identity. Preserve the reported failure instead of picking a winner.
            row = candidates[0] if len(candidates) == 1 and item.get("link") else {}
            if len(candidates) > 1:
                item["identity_note"] = "ambiguous_check_identity"
            if row and row.get("head_sha") != head:
                raise QueryFailure("check_source_sha_mismatch")
            item.update(check_id=row.get("id"), head_sha=row.get("head_sha"),
                        app_id=(row.get("app") or {}).get("id"))
            if row:
                bucket = check_bucket(row)
                if item["bucket"] != bucket:
                    item["reported_bucket"] = item["bucket"]
                    item["bucket"] = bucket
            matches = [status for status in statuses if status.get("context") == item["name"]
                       and status.get("target_url") == item.get("link")]
            if not candidates and len(matches) == 1:
                bucket = {"success": "pass", "failure": "fail", "error": "fail", "pending": "pending"}.get(matches[0].get("state"))
                if bucket:
                    item.update(head_sha=head, bucket=bucket)
            link = urlparse(item.get("link") or "")
            match = re.fullmatch(
                rf"/{re.escape(repository)}/actions/runs/(\d+)(?:/job/(\d+))?", link.path,
            ) if link.hostname == host else None
            if match:
                item["run_id"] = int(match[1])
        needed = set(run_ids) | {item["run_id"] for item in checks if "run_id" in item
                                and (item["required"] or item["bucket"] != "pass")}
        for run_id in sorted(needed):
            run = api(query, host, f"repos/{repository}/actions/runs/{run_id}")
            if not isinstance(run, dict) or run.get("head_sha") != head or run.get("id") != run_id:
                raise QueryFailure("run_source_sha_mismatch")
            attempt = run.get("run_attempt")
            if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt <= 0:
                raise QueryFailure("missing_run_attempt")
            detail = {key: run.get(key) for key in (
                "id", "head_sha", "event", "head_branch", "run_attempt", "status", "conclusion", "html_url"
            )}
            detail["id"] = run_id
            jobs = query([
                "api", f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100",
                "--hostname", host, "--paginate", "--slurp",
            ])
            jobs = pages(jobs, "jobs")
            detail["jobs"] = [job_stage(job) for job in jobs
                              if job.get("conclusion") not in {"success", "skipped"}]
            detail["current_job_ids"] = [job.get("id") for job in jobs]
            runs[run_id] = detail
        for item in checks:
            run = runs.get(item.get("run_id"), {})
            match = re.search(r"/job/(\d+)$", item.get("link") or "")
            current_attempt = not match or int(match[1]) in run.get("current_job_ids", [])
            item.update(event=run.get("event"), attempt=run.get("run_attempt") if current_attempt else None)
            if run and not current_attempt:
                item["attempt_note"] = "check_is_not_in_current_run_attempt"
        for run in runs.values():
            run.pop("current_job_ids", None)
    duplicates = {name for name, count in Counter(row["name"] for row in checks).items() if count > 1}
    return {
        "required": [row for row in checks if row["required"]],
        "additional": [row for row in checks if not row["required"]],
        "checks": checks, "runs": list(runs.values()), "ambiguous_check_names": sorted(duplicates),
        "rerun_guidance": "verify_event_sha_attempt_and_failure_stage" if duplicates or
        any(row["bucket"] in {"fail", "cancel"} for row in checks) else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("repository", type=repository_name)
    pre.add_argument("--source-repository", type=repository_name)
    pre.add_argument("--hostname", default="github.com")
    pre.add_argument("--base")
    diagnostic = sub.add_parser("diagnose")
    diagnostic.add_argument("pr_url")
    diagnostic.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    try:
        def query(arguments):
            return query_json(arguments, 30)
        if args.command == "preflight":
            result = preflight(args.repository, query, host=args.hostname, base=args.base,
                               source=args.source_repository, capabilities=cli_capabilities())
        else:
            if not SHA_PATTERN.fullmatch(args.expected_head):
                raise ValueError("expected-head must be a full commit SHA")
            result = checks_snapshot(args.pr_url, args.expected_head, query)
    except (QueryFailure, FileNotFoundError, ValueError, subprocess.TimeoutExpired) as error:
        reason = "gh_not_installed" if isinstance(error, FileNotFoundError) else str(error)
        if isinstance(error, QueryFailure) and error.http_status == 401:
            reason = "github_login_required"
        print(json.dumps({"status": "unverified", "reason": reason}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result.get("status", "ready") == "ready" else 3


if __name__ == "__main__":
    raise SystemExit(main())
