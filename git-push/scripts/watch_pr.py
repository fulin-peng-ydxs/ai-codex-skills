#!/usr/bin/env python3
"""Bounded PR monitoring with separate merge/validation outcomes and resumable checkpoints."""

import argparse
import json
import subprocess
import time
from copy import deepcopy
from pathlib import Path

from github_pr import (
    PR_FIELDS,
    SHA_PATTERN,
    QueryFailure,
    checks_snapshot,
    outcome,
    parse_pr_url,
    query_json,
)
from pr_state import (
    checkpoint_wait,
    choose_budget,
    private_path,
    save_state,
    seconds,
    start_wait,
)

DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_INTERVAL_SECONDS = 60


def verified_outcome(checks, expected_head):
    """Retain observed failures, but require source identity before claiming success."""
    status = outcome(checks)
    if status == "passed" and any(row.get("head_sha") != expected_head for row in checks):
        return "unverified"
    return status


def inspect_pr(pr_url, expected_head, query, *, expected_base=None, scope="required",
               run_ids=(), wait_for_review=False):
    """A platform merge, successful checks and local cleanup are independent facts."""
    pr = query(["pr", "view", pr_url, "--json", PR_FIELDS])
    if not isinstance(pr, dict) or pr.get("state") not in {"OPEN", "CLOSED", "MERGED"}:
        raise QueryFailure("invalid_pr_state")
    head = pr.get("headRefOid")
    if not isinstance(head, str) or not SHA_PATTERN.fullmatch(head):
        raise QueryFailure("missing_pr_head")
    if pr.get("url", pr_url).rstrip("/") != pr_url.rstrip("/"):
        raise QueryFailure("pr_identity_mismatch")
    details = {
        "head_sha": head, "base_branch": pr.get("baseRefName"),
        "head_branch": pr.get("headRefName"), "merge_status": pr["state"].lower(),
        "validation_status": "unverified", "cleanup_allowed": False,
        "review_decision": pr.get("reviewDecision"),
    }
    if head.lower() != expected_head.lower():
        return "head_changed", details
    if expected_base and pr.get("baseRefName") != expected_base:
        return "target_changed", details
    if pr["state"] == "MERGED":
        commit = pr.get("mergeCommit")
        sha = commit.get("oid") if isinstance(commit, dict) else None
        if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha) or not pr.get("mergedAt"):
            raise QueryFailure("incomplete_merge_evidence")
        details.update(merge_sha=sha, merged_at=pr["mergedAt"], cleanup_allowed=True)
    elif pr["state"] == "CLOSED":
        return "closed_unmerged", details
    elif not isinstance(pr.get("isDraft"), bool):
        raise QueryFailure("missing_draft_state")
    elif pr["isDraft"]:
        return "draft", details
    elif pr.get("mergeable") == "CONFLICTING":
        return "conflict", details
    elif pr.get("reviewDecision") == "CHANGES_REQUESTED":
        return "changes_requested", details
    elif pr.get("reviewDecision") == "REVIEW_REQUIRED" and not wait_for_review:
        return "review_required", details
    try:
        checks = checks_snapshot(pr_url, expected_head, query, run_ids=run_ids)
    except (QueryFailure, OSError) as error:
        if not details["cleanup_allowed"]:
            raise
        details["diagnostic_error"] = "gh_not_installed" if isinstance(error, FileNotFoundError) else str(error)
        return "merged", details
    required_status = verified_outcome(checks["required"], expected_head)
    selected = checks["checks"] if scope == "all" else checks["required"]
    tracked = checks["runs"] if run_ids else []
    tracked = [run for run in tracked if run["id"] in run_ids]
    run_checks = [{"head_sha": run["head_sha"],
                   "bucket": "pending" if run["status"] != "completed" else
                   "pass" if run["conclusion"] == "success" else
                   "skipping" if run["conclusion"] == "skipped" else "fail"}
                  for run in tracked]
    selected_status = verified_outcome([*selected, *run_checks], expected_head)
    details.update(
        required_checks_status=required_status, validation_status=selected_status,
        additional_checks_status=verified_outcome(checks["additional"], expected_head),
        check_counts={bucket: sum(row["bucket"] == bucket for row in checks["checks"])
                      for bucket in ("pass", "pending", "fail", "cancel", "skipping")},
        failed_checks=[row for row in checks["checks"] if row["bucket"] in {"fail", "cancel"}],
        pending_checks=[row for row in checks["checks"] if row["bucket"] == "pending"],
        runs=checks["runs"], ambiguous_check_names=checks["ambiguous_check_names"],
        rerun_guidance=checks["rerun_guidance"],
    )
    if details["cleanup_allowed"]:
        return "merged", details
    if required_status == "failed" or selected_status == "failed":
        return "checks_failed", details
    return "pending", details


def watch_pr(pr_url, expected_head, timeout_seconds=None, interval_seconds=60, *,
             query=query_json, now=time.monotonic, sleep=time.sleep, wall=time.time,
             state=None, state_path=None, ci_timeout=None, ceiling=3600, new_round=False,
             extend=0, expected_base=None, scope="required", run_ids=(), completion="merge",
             wait_for_review=False, emit=None, allow_goal_change=False):
    """Retries and process restarts consume one budget; user limits are never auto-extended."""
    parse_pr_url(pr_url)
    if not SHA_PATTERN.fullmatch(expected_head):
        raise ValueError("expected-head must be a full commit SHA")
    expected_head = expected_head.lower()
    if scope not in {"required", "all"} or completion not in {"merge", "validation"}:
        raise ValueError("invalid monitoring goal")
    if any(isinstance(run, bool) or not isinstance(run, int) or run <= 0 for run in run_ids):
        raise ValueError("run IDs must be positive integers")
    interval_seconds = seconds(interval_seconds)
    if interval_seconds > 60:
        raise ValueError("interval must not exceed 60 seconds")
    state = {} if state is None else state
    if not isinstance(state, dict):
        raise TypeError("invalid state document")
    if state.get("version", 1) != 1:
        raise ValueError("invalid state version")
    previous = state.get("watch", {})
    if not isinstance(previous, dict):
        raise TypeError("invalid watch checkpoint")
    old_scope = previous.get("scope")
    selected_scope = {"checks": scope, "run_ids": list(run_ids), "completion": completion}
    goal_change = None
    if old_scope is not None:
        if (not isinstance(old_scope, dict) or old_scope.get("checks") not in {"required", "all"}
                or old_scope.get("completion") not in {"merge", "validation"}
                or not isinstance(old_scope.get("run_ids"), list)):
            raise ValueError("invalid saved verification scope")
        narrowing = (old_scope.get("checks") == "all" and scope != "all") or (
            old_scope.get("completion") == "validation" and completion != "validation"
        ) or not set(old_scope.get("run_ids", [])).issubset(run_ids)
        if narrowing and not allow_goal_change:
            raise ValueError("narrowing verification requires an explicit user goal change")
        if narrowing:
            if not isinstance(state.get("goal_changes", []), list):
                raise ValueError("invalid goal-change history")
            # A removed run may disappear entirely from the next snapshot. Keep
            # the old conclusion and its SHA/run/attempt before replacing latest.
            goal_change = deepcopy({
                "previous": old_scope, "current": selected_scope,
                "identity": previous.get("identity"),
                "last_status": previous.get("last_status"),
                "latest": previous.get("latest"),
            })
    original_base = previous.get("base_branch")
    if expected_base and original_base and expected_base != original_base:
        raise ValueError("target branch changed in the saved watch")
    context = state.setdefault("context", {"pr_url": pr_url, "source_sha": expected_head})
    if not isinstance(context, dict) or context.get("pr_url") != pr_url:
        raise ValueError("state belongs to a different PR")
    allowed = context.get("allowed_commits")
    if allowed is not None and (
        not isinstance(allowed, list) or expected_head not in allowed
        or any(not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha) for sha in allowed)
    ):
        raise ValueError("source is outside the reviewed commit list")
    if context.get("source_sha") != expected_head:
        if not new_round or context.get("merge_sha"):
            raise ValueError("source SHA changed outside a verified open-PR repair round")
        context["source_sha"] = expected_head
    if new_round and context.get("merge_sha"):
        raise ValueError("a merged PR cannot start a new source round")
    state.setdefault("version", 1)
    state.setdefault("phase", "watching")
    if state["phase"] == "preparing":
        state["phase"] = "watching"
    budget, basis = choose_budget(timeout_seconds, ci_timeout, ceiling)
    started = now()
    deadline = start_wait(state, {"url": pr_url, "head": expected_head}, budget, basis,
                          wall(), started, new_round=new_round, extend=extend)
    record = state["watch"]
    saved_base = record.get("base_branch") or original_base
    if expected_base and saved_base and expected_base != saved_base:
        raise ValueError("target branch changed in the saved watch")
    expected_base = expected_base or saved_base
    if goal_change is not None:
        state.setdefault("goal_changes", []).append(goal_change)
    record["scope"] = selected_scope
    polls, failures, details = 0, 0, record.get("latest", {})
    if new_round:
        details = {}
    previous_signature = record.get("progress_signature")

    def persist():
        checkpoint_wait(state, deadline, now())
        if state_path is not None:
            save_state(state_path, state)

    def finish(status, code):
        record["last_status"] = status
        persist()
        return code, {
            "status": status, "pr_url": pr_url, "completion_goal": completion,
            "verification_scope": selected_scope,
            "elapsed_seconds": round(now() - started, 2), "polls": polls,
            "remaining_seconds": round(max(0, deadline - now()), 2), **details,
        }

    def bounded_query(arguments):
        remaining = deadline - now()
        if remaining <= 0:
            raise QueryFailure("deadline_reached")
        return query(arguments, min(30, remaining))

    persist()
    while now() < deadline:
        polls += 1
        try:
            status, current = inspect_pr(
                pr_url, expected_head, bounded_query, expected_base=expected_base,
                scope=scope, run_ids=run_ids, wait_for_review=wait_for_review,
            )
            details = current
            failures = failures + 1 if current.get("diagnostic_error") and completion == "validation" else 0
            if status not in {"head_changed", "target_changed"}:
                expected_base = expected_base or details.get("base_branch")
                record["base_branch"] = expected_base
            record["latest"] = details
            if details.get("cleanup_allowed"):
                context.update(merge_sha=details["merge_sha"], merged_at=details["merged_at"])
                if state["phase"] == "watching":
                    state["phase"] = "pending"
            details["acceptance_complete"] = details.get("validation_status") == "passed"
            signature = json.dumps({"status": status, **details}, sort_keys=True)
            if emit and signature != previous_signature:
                emit({"event": "progress", "status": status, **details})
            previous_signature = signature
            record["progress_signature"] = signature
            persist()
            if failures >= 3:
                return finish("query_error", 2)
            if status == "merged":
                if completion == "merge" or details["acceptance_complete"]:
                    return finish("merged", 0)
                if details.get("validation_status") in {"failed", "incomplete"}:
                    return finish("validation_failed", 1)
            elif status == "review_required":
                return finish(status, 3)
            elif status != "pending":
                return finish(status, 1)
        except FileNotFoundError:
            details = {**details, "reason": "gh_not_installed"}
            return finish("query_error", 2)
        except (QueryFailure, OSError) as error:
            failures += 1
            details = {**details, "reason": str(error)}
            record["latest"] = details
            persist()
            if failures >= 3:
                return finish("query_error", 2)
        remaining = deadline - now()
        if remaining > 0:
            sleep(min(interval_seconds, remaining))
    return finish("timeout", 8)


def positive_seconds(value):
    try:
        return seconds(float(value))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr_url")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-base")
    parser.add_argument("--timeout-seconds", type=positive_seconds)
    parser.add_argument("--ci-timeout-seconds", type=positive_seconds)
    parser.add_argument("--max-wait-seconds", type=positive_seconds, default=3600)
    parser.add_argument("--interval-seconds", type=positive_seconds, default=60)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--new-round", action="store_true")
    parser.add_argument("--extend-seconds", type=positive_seconds, default=0)
    parser.add_argument("--checks-scope", choices=("required", "all"), default="required")
    parser.add_argument("--run-id", type=int, action="append", default=[])
    parser.add_argument("--completion", choices=("merge", "validation"), default="merge")
    parser.add_argument("--wait-for-review", action="store_true")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--allow-goal-change", action="store_true")
    args = parser.parse_args()
    try:
        path = private_path(args.repo, args.state) if args.state else None
        state = json.loads(path.read_text()) if path and path.exists() else None
        emit = (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True)) if args.progress else None
        code, result = watch_pr(
            args.pr_url, args.expected_head, args.timeout_seconds, args.interval_seconds,
            state=state, state_path=path, ci_timeout=args.ci_timeout_seconds,
            ceiling=args.max_wait_seconds, new_round=args.new_round, extend=args.extend_seconds,
            expected_base=args.expected_base, scope=args.checks_scope, run_ids=tuple(args.run_id),
            completion=args.completion, wait_for_review=args.wait_for_review, emit=emit,
            allow_goal_change=args.allow_goal_change,
        )
    except KeyboardInterrupt:
        code, result = 130, {"status": "interrupted", "pr_url": args.pr_url}
    except (ValueError, TypeError, OSError, subprocess.SubprocessError) as error:
        code, result = 2, {"status": "query_error", "reason": str(error)}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
