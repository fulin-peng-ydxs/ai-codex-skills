#!/usr/bin/env python3
"""Read-only, bounded PR polling; print one compact result instead of every snapshot."""

import argparse
import json
import math
import re
import subprocess
import time
from urllib.parse import urlparse

DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_INTERVAL_SECONDS = 60
PR_FIELDS = (
    "state,mergedAt,mergeCommit,headRefOid,headRefName,baseRefName,mergeable,isDraft,reviewDecision"
)
SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")


class QueryFailure(Exception):
    """A snapshot could not be trusted; never interpret it as a PR conclusion."""


def query_json(arguments, timeout):
    """Keep gh output local and pass arguments without shell interpolation."""
    try:
        completed = subprocess.run(
            ["gh", *arguments], capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as error:
        raise QueryFailure("gh_command_timeout") from error
    # FileNotFoundError is handled immediately by the watcher rather than retried.
    checks = arguments[:2] == ["pr", "checks"]
    if (
        checks
        and completed.returncode == 1
        and not completed.stdout.strip()
        and completed.stderr.lower()
        .strip()
        .startswith(("no checks reported", "no required checks reported"))
    ):
        return []
    # Pending (8) and failing (1) checks can still carry a usable JSON snapshot.
    allowed = (0, 1, 8) if checks else (0,)
    if completed.returncode not in allowed or (
        completed.returncode == 1 and not completed.stdout.strip()
    ):
        raise QueryFailure(f"gh_{arguments[1]}_exit_{completed.returncode}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise QueryFailure("invalid_gh_json") from error


def inspect_pr(pr_url, expected_head, query):
    """Only actual merged evidence authorizes the caller to start local cleanup."""
    pr = query(["pr", "view", pr_url, "--json", PR_FIELDS])
    if not isinstance(pr, dict) or pr.get("state") not in {"OPEN", "CLOSED", "MERGED"}:
        raise QueryFailure("invalid_pr_state")
    head = pr.get("headRefOid")
    if not isinstance(head, str) or not SHA_PATTERN.fullmatch(head):
        raise QueryFailure("missing_pr_head")
    details = {
        "head_sha": head,
        "base_branch": pr.get("baseRefName"),
        "head_branch": pr.get("headRefName"),
    }
    if head.lower() != expected_head.lower():
        return "head_changed", details
    if pr["state"] == "MERGED":
        commit = pr.get("mergeCommit")
        sha = commit.get("oid") if isinstance(commit, dict) else None
        if (
            not isinstance(sha, str)
            or not SHA_PATTERN.fullmatch(sha)
            or not isinstance(pr.get("mergedAt"), str)
            or not pr["mergedAt"]
        ):
            raise QueryFailure("incomplete_merge_evidence")
        return "merged", {**details, "merge_sha": sha, "merged_at": pr["mergedAt"]}
    if pr["state"] == "CLOSED":
        return "closed_unmerged", details
    if not isinstance(pr.get("isDraft"), bool):
        raise QueryFailure("missing_draft_state")
    if pr["isDraft"]:
        return "draft", details
    if pr.get("mergeable") == "CONFLICTING":
        return "conflict", details
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        return "changes_requested", details
    checks = query(["pr", "checks", pr_url, "--required", "--json", "name,bucket,link"])
    if not isinstance(checks, list) or any(
        not isinstance(check, dict)
        or check.get("bucket") not in {"pass", "fail", "pending", "skipping", "cancel"}
        for check in checks
    ):
        raise QueryFailure("invalid_required_checks")
    failures = [
        {key: check.get(key) for key in ("name", "bucket", "link")}
        for check in checks
        if check["bucket"] in {"fail", "cancel"}
    ]
    if failures:
        return "checks_failed", {**details, "failed_checks": failures}
    # Passing checks, or no required checks, never prove that the PR was merged.
    return "pending", details


def watch_pr(
    pr_url,
    expected_head,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    interval_seconds=DEFAULT_INTERVAL_SECONDS,
    *,
    query=query_json,
    now=time.monotonic,
    sleep=time.sleep,
):
    """Use one deadline, with at most three consecutive query failures."""
    started = now()
    deadline = started + timeout_seconds
    polls = 0
    failures = 0
    details = {}

    def finish(status, code):
        return code, {
            "status": status,
            "pr_url": pr_url,
            "elapsed_seconds": round(now() - started, 2),
            "polls": polls,
            **details,
        }

    def bounded_query(arguments):
        remaining = deadline - now()
        if remaining <= 0:
            raise QueryFailure("deadline_reached")
        return query(arguments, min(30, remaining))

    while now() < deadline:
        polls += 1
        try:
            status, details = inspect_pr(pr_url, expected_head, bounded_query)
            failures = 0
        except FileNotFoundError:
            details = {"reason": "gh_not_installed"}
            return finish("query_error", 2)
        except (QueryFailure, OSError) as error:
            failures += 1
            details = {"reason": str(error) if isinstance(error, QueryFailure) else "gh_os_error"}
            if failures >= 3:
                return finish("query_error", 2)
        else:
            if status == "merged":
                return finish(status, 0)
            if status != "pending":
                return finish(status, 1)
        remaining = deadline - now()
        if remaining > 0:
            sleep(min(interval_seconds, 60, remaining))
    return finish("timeout", 8)


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("seconds must be finite and greater than zero")
    return seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr_url")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--interval-seconds", type=positive_seconds, default=DEFAULT_INTERVAL_SECONDS
    )
    args = parser.parse_args()
    url = urlparse(args.pr_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or not re.fullmatch(r"/[^/]+/[^/]+/pull/[1-9][0-9]*/?", url.path)
    ):
        parser.error("pr_url must be an HTTPS pull request URL")
    if not SHA_PATTERN.fullmatch(args.expected_head):
        parser.error("expected-head must be a full commit SHA")
    if args.interval_seconds > 60:
        parser.error("interval-seconds must not exceed 60")
    try:
        code, result = watch_pr(
            args.pr_url, args.expected_head, args.timeout_seconds, args.interval_seconds
        )
    except KeyboardInterrupt:
        code, result = 130, {"status": "interrupted", "pr_url": args.pr_url}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
