#!/usr/bin/env python3
"""Finish a verified merged PR locally, with recoverable sync and cleanup checkpoints."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


class FinishError(Exception):
    """Local evidence or a Git operation did not meet the cleanup contract."""


def git(repo, *arguments, allow=(0,)):
    result = subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode not in allow:
        raise FinishError(f"git {arguments[0]} failed: {result.stderr.strip()[:300]}")
    return result


def ref_sha(repo, ref):
    result = git(repo, "rev-parse", "--verify", "--quiet", ref, allow=(0, 1))
    return result.stdout.strip() if result.returncode == 0 else None


def ancestor(repo, older, newer):
    return git(repo, "merge-base", "--is-ancestor", older, newer, allow=(0, 1)).returncode == 0


def save_state(path, state):
    """Persist intent before Git writes; atomic replacement keeps prior checkpoints usable."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as f:
            temporary = Path(f.name)
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_state(repo, state):
    if state.get("version") != 1 or state.get("phase") not in {
        "pending",
        "syncing",
        "synced",
        "cleaning",
        "complete",
    }:
        raise FinishError("invalid state version or phase")
    context = state.get("context")
    if not isinstance(context, dict) or not context.get("pr_url") or not context.get("merged_at"):
        raise FinishError("verified PR identity and merge time are required")
    for name in ("return_branch", "work_branch"):
        value = context.get(name)
        if not isinstance(value, str):
            raise FinishError(f"missing {name}")
        git(repo, "check-ref-format", "--branch", value)
    if context["return_branch"] == context["work_branch"]:
        raise FinishError("the return branch must not be the cleanup branch")
    for name in ("return_upstream", "target_ref"):
        value = context.get(name)
        if not isinstance(value, str) or not value.startswith("refs/remotes/"):
            raise FinishError(f"{name} must be a verified remote-tracking ref")
        git(repo, "check-ref-format", value)
    sha_pattern = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
    for name in ("return_sha", "source_sha", "merge_sha"):
        if not isinstance(context.get(name), str) or not sha_pattern.fullmatch(context[name]):
            raise FinishError(f"invalid {name}")
    allowed = context.get("allowed_commits")
    if (
        not isinstance(allowed, list)
        or not allowed
        or any(not isinstance(sha, str) or not sha_pattern.fullmatch(sha) for sha in allowed)
    ):
        raise FinishError("allowed_commits must contain the reviewed task commit SHAs")
    if context["source_sha"] not in allowed:
        raise FinishError("verified source is outside the reviewed task commits")
    if state["phase"] == "syncing":
        intent = state.get("sync_intent")
        if not isinstance(intent, dict) or any(
            not isinstance(intent.get(key), str) or not sha_pattern.fullmatch(intent[key])
            for key in ("from", "to")
        ):
            raise FinishError("invalid saved synchronization intent")
    if state["phase"] in {"synced", "cleaning", "complete"}:
        if not isinstance(state.get("synced_sha"), str) or not sha_pattern.fullmatch(
            state["synced_sha"]
        ):
            raise FinishError("missing completed synchronization SHA")
    return context


def check_local_state(repo, context):
    if git(repo, "status", "--porcelain", "--untracked-files=normal").stdout.strip():
        raise FinishError("working tree or index is not clean")
    current = git(repo, "branch", "--show-current").stdout.strip()
    if current not in {context["return_branch"], context["work_branch"]}:
        raise FinishError("current branch is outside this PR workflow")
    worktree_path = None
    protected = {f"refs/heads/{context[name]}" for name in ("return_branch", "work_branch")}
    for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            worktree_path = Path(line[9:]).resolve()
        elif line.startswith("branch ") and line[7:] in protected and worktree_path != repo:
            raise FinishError("a workflow branch is in use by another worktree")
    work = ref_sha(repo, f"refs/heads/{context['work_branch']}")
    if work is not None and work != context["source_sha"]:
        raise FinishError("work branch changed after the verified push")
    target = ref_sha(repo, context["target_ref"])
    if target is None or not ancestor(repo, context["merge_sha"], target):
        raise FinishError("PR merge commit is not reachable from its target")
    if not ancestor(repo, context["source_sha"], context["merge_sha"]):
        raise FinishError("verified source commits are not in the PR merge commit")
    return work


def sync_plan(repo, context, current):
    upstream = ref_sha(repo, context["return_upstream"])
    if upstream is None:
        raise FinishError("return upstream is missing")
    if current == upstream or ancestor(repo, current, upstream):
        return upstream, "fast_forward" if current != upstream else "equal", 0
    if context["return_upstream"] != context["target_ref"] and ancestor(repo, upstream, current):
        ahead = set(git(repo, "rev-list", f"{upstream}..{current}").stdout.splitlines())
        if ahead <= set(context["allowed_commits"]) and ancestor(
            repo, current, context["merge_sha"]
        ):
            return current, "ahead", len(ahead)
    raise FinishError("return branch diverged or has unapproved ahead commits")


def finish_pr(repo, path):
    """The caller verifies platform merge evidence and fetches refs before invoking this."""
    repo = Path(git(repo, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    common = Path(
        git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    )
    path = Path(path).resolve()
    if not path.is_relative_to(common.resolve() / "codex" / "pr-push"):
        raise FinishError("state must be inside this repository's private PR metadata directory")
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise FinishError("invalid state document")
    context = validate_state(repo, state)
    work = check_local_state(repo, context)
    original_ref = f"refs/heads/{context['return_branch']}"
    original = ref_sha(repo, original_ref)
    if original is None:
        raise FinishError("original return branch is missing")

    if state["phase"] == "complete":
        if original != state.get("synced_sha") or work is not None:
            raise FinishError(
                "completed workflow branches changed or were recreated; preserve them"
            )
        return {"status": "complete", "cleanup": "already_complete", "synced_sha": original}

    if state["phase"] == "syncing":
        intent = state.get("sync_intent", {})
        if original not in {intent.get("from"), intent.get("to")}:
            raise FinishError("return branch no longer matches the saved sync intent")
        if original == intent.get("from"):
            # A failed or interrupted command can be retried against its pinned target.
            if not ancestor(repo, original, intent["to"]):
                raise FinishError("saved sync intent is not a fast-forward")
            git(repo, "switch", context["return_branch"])
            git(repo, "merge", "--ff-only", intent["to"])
        state.update(phase="synced", synced_sha=intent["to"])
        save_state(path, state)
        original = intent["to"]

    expected = context["return_sha"] if state["phase"] == "pending" else state.get("synced_sha")
    if original != expected:
        raise FinishError("return branch changed outside the saved workflow progress")
    desired, mode, ahead_count = sync_plan(repo, context, original)
    if desired != original or state["phase"] == "pending":
        state.update(phase="syncing", sync_intent={"from": original, "to": desired})
        save_state(path, state)
        git(repo, "switch", context["return_branch"])
        if desired != original:
            git(repo, "merge", "--ff-only", desired)
        state.update(phase="synced", synced_sha=desired)
        save_state(path, state)
    else:
        git(repo, "switch", context["return_branch"])

    work = check_local_state(repo, context)
    if ref_sha(repo, original_ref) != state["synced_sha"]:
        raise FinishError("return branch changed after synchronization")
    final_target, _, _ = sync_plan(repo, context, state["synced_sha"])
    if final_target != state["synced_sha"]:
        raise FinishError("return upstream advanced during finalization; retry with saved progress")
    state.update(phase="cleaning")
    save_state(path, state)
    if git(repo, "branch", "--show-current").stdout.strip() != context["return_branch"]:
        raise FinishError("current branch changed before cleanup")
    if work is not None:
        # The merged-to ref is the PR target, which need not be the checked-out branch.
        # Compare-and-delete prevents deleting a source ref that changed after verification.
        git(repo, "update-ref", "-d", f"refs/heads/{context['work_branch']}", context["source_sha"])
    if ref_sha(repo, f"refs/heads/{context['work_branch']}") is not None:
        raise FinishError("work branch was recreated; preserve it")
    section = f"branch.{context['work_branch']}"
    config = git(
        repo, "config", "--local", "--get-regexp", f"^{re.escape(section)}\\.", allow=(0, 1)
    )
    if config.returncode == 0:
        git(repo, "config", "--local", "--remove-section", section)
    state.update(phase="complete", cleanup="deleted" if work is not None else "already_absent")
    save_state(path, state)
    return {
        "status": "complete",
        "cleanup": state["cleanup"],
        "return_branch": context["return_branch"],
        "synced_sha": state["synced_sha"],
        "sync_mode": mode,
        "ahead_count": ahead_count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--repo", default=".", type=Path)
    args = parser.parse_args()
    try:
        result = finish_pr(args.repo, args.state)
    except (FinishError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "incomplete", "reason": str(error)}, ensure_ascii=False))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "state": str(args.state)}))
        return 130
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
