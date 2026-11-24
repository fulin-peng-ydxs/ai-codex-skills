#!/usr/bin/env python3
"""Finish a verified merged PR locally, with recoverable sync and cleanup checkpoints."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


class FinishError(Exception):
    """Local evidence or a Git operation did not meet the cleanup contract."""


def git(repo, *arguments, allow=(0,), env=None):
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    if result.returncode not in allow:
        raise FinishError(f"git {arguments[0]} failed: {result.stderr.strip()[:300]}")
    return result


def ref_sha(repo, ref):
    result = git(repo, "rev-parse", "--verify", "--quiet", ref, allow=(0, 1))
    return result.stdout.strip() if result.returncode == 0 else None


def ancestor(repo, older, newer):
    return git(repo, "merge-base", "--is-ancestor", older, newer, allow=(0, 1)).returncode == 0


def worktrees(repo):
    """Use the same NUL-delimited inventory for preflight and in-transaction occupancy checks."""
    for block in git(repo, "worktree", "list", "--porcelain", "-z").stdout.split("\0\0"):
        fields = dict(field.partition(" ")[::2] for field in block.split("\0") if field)
        if fields:
            if "worktree" not in fields:
                raise FinishError("invalid Git worktree inventory")
            yield Path(fields["worktree"]).resolve(), fields.get("branch")


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
    protected = {f"refs/heads/{context[name]}" for name in ("return_branch", "work_branch")}
    for worktree_path, branch in worktrees(repo):
        if branch in protected and worktree_path != repo:
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


def verification_path(path, token):
    """Only task-private detached worktrees may be created or removed by finalization."""
    return path.parent / f"verification-{token}"


def check_verification(repo, path, context):
    if git(path, "rev-parse", "HEAD").stdout.strip() != context["merge_sha"]:
        raise FinishError("private verification worktree HEAD changed; preserve it")
    if git(path, "branch", "--show-current").stdout.strip():
        raise FinishError("private verification worktree is no longer detached; preserve it")
    if git(path, "status", "--porcelain", "--untracked-files=normal").stdout.strip():
        raise FinishError("private verification worktree has changes; preserve it")
    if Path(git(path, "rev-parse", "--show-toplevel").stdout.strip()).resolve() != path:
        raise FinishError("private verification worktree identity changed")
    if (
        git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
        != git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    ):
        raise FinishError("private verification worktree belongs to another repository")


def native_delete(repo, path, state, context):
    """Use Git's occupancy protection and PR-merge ancestry, with an in-transaction SHA guard."""
    token = state["delete_token"]
    verification = verification_path(path, token)
    if not verification.exists():
        git(repo, "worktree", "add", "--detach", str(verification), context["merge_sha"])
    check_verification(repo, verification, context)
    check_local_state(repo, context)
    hook_path = Path(
        git(repo, "rev-parse", "--git-path", "hooks/reference-transaction").stdout.strip()
    )
    if not hook_path.is_absolute():
        hook_path = repo / hook_path
    guard = Path(__file__).resolve().with_name("guard_branch_delete.py")
    with tempfile.TemporaryDirectory(prefix=f"guard-{token}-", dir=path.parent) as hooks:
        wrapper = Path(hooks) / "reference-transaction"
        wrapper.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -B {shlex.quote(str(guard))} "$@"\n'
        )
        wrapper.chmod(0o700)
        env = {
            **os.environ,
            "CODEX_PR_DELETE_REF": f"refs/heads/{context['work_branch']}",
            "CODEX_PR_DELETE_SHA": context["source_sha"],
            "CODEX_PR_DELETE_TOKEN": token,
            "CODEX_PR_DELETE_RECEIPT": str(path.parent / f"deleted-{token}.json"),
            "CODEX_PR_ORIGINAL_REF_HOOK": str(hook_path),
        }
        # A nonexistent per-command upstream makes -d use this detached PR merge HEAD.
        # No persistent branch configuration is changed and no force-delete option is used.
        state["delete_dispatched"] = True
        save_state(path, state)
        git(
            verification,
            "-c",
            f"core.hooksPath={hooks}",
            "-c",
            f"branch.{context['work_branch']}.remote=codex-unconfigured-{token}",
            "branch",
            "-d",
            "--",
            context["work_branch"],
            env=env,
        )


def remove_verification(repo, path, state, context):
    token = state.get("delete_token")
    if token:
        verification = verification_path(path, token)
        if verification.exists():
            check_verification(repo, verification, context)
            git(repo, "worktree", "remove", str(verification))


def check_cleanup_identity(path, state, context, work):
    """A deletion attempt stays binding across sync retries, regardless of the current phase."""
    token = state.get("delete_token")
    if token is not None and (
        not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token)
    ):
        raise FinishError("invalid cleanup token")
    # Legacy cleanup records cannot prove a deletion was never dispatched.
    if "delete_dispatched" not in state and (token or state["phase"] == "cleaning"):
        state["delete_dispatched"] = True
    receipt = path.parent / f"deleted-{token}.json" if token else None
    if receipt is not None and receipt.exists():
        expected = {
            "token": token,
            "ref": f"refs/heads/{context['work_branch']}",
            "sha": context["source_sha"],
        }
        if json.loads(receipt.read_text()) != expected:
            raise FinishError("deletion receipt does not match this PR workflow")
        if work is not None:
            raise FinishError("work branch was recreated after deletion; preserve it")
    if work is not None and state.get("delete_dispatched", False):
        raise FinishError(
            "previous deletion outcome is ambiguous or branch was recreated; preserve it"
        )


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

    check_cleanup_identity(path, state, context, work)

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
    else:
        expected = context["return_sha"] if state["phase"] == "pending" else state.get("synced_sha")
        if original != expected:
            raise FinishError("return branch changed outside the saved workflow progress")
    # Initial and resumed synchronization share one validated plan and one write sequence.
    desired, mode, ahead_count = sync_plan(repo, context, original)
    if desired != original or state["phase"] in {"pending", "syncing"}:
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
    check_cleanup_identity(path, state, context, work)
    if ref_sha(repo, original_ref) != state["synced_sha"]:
        raise FinishError("return branch changed after synchronization")
    final_target, _, _ = sync_plan(repo, context, state["synced_sha"])
    if final_target != state["synced_sha"]:
        raise FinishError("return upstream advanced during finalization; retry with saved progress")
    state.setdefault("delete_dispatched", False)
    state.update(phase="cleaning")
    state.setdefault("delete_token", uuid.uuid4().hex)
    save_state(path, state)
    if git(repo, "branch", "--show-current").stdout.strip() != context["return_branch"]:
        raise FinishError("current branch changed before cleanup")
    if work is not None:
        native_delete(repo, path, state, context)
    if ref_sha(repo, f"refs/heads/{context['work_branch']}") is not None:
        raise FinishError("work branch was recreated; preserve it")
    # Native branch deletion removes its own config. Never remove a recreated branch's config.
    remove_verification(repo, path, state, context)
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
