"""Private PR checkpoints and bounded wait budgets shared by monitoring and cleanup."""

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

DEFAULT_WAIT = 1800
DEFAULT_CEILING = 3600
QUEUE_AND_RESULT_GRACE = 300


def save_state(path, state):
    """Atomic replacement retains the previous checkpoint on a failed write."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            json.dump(state, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def private_path(repo, path):
    """Watch and cleanup records belong to the same repository-private directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=repo, text=True, capture_output=True, check=True, timeout=30,
    )
    root = Path(result.stdout.strip()).resolve() / "codex" / "pr-push"
    path = Path(path).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("state must be inside this repository's private PR metadata directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("wait budget must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("wait budget must be a positive finite number")
    return float(value)


def choose_budget(explicit=None, ci_timeout=None, ceiling=DEFAULT_CEILING):
    """An explicit user limit wins; otherwise include bounded queue/result headroom."""
    if explicit is not None:
        return seconds(explicit), "explicit"
    ceiling = seconds(ceiling)
    requested = DEFAULT_WAIT if ci_timeout is None else max(
        DEFAULT_WAIT, seconds(ci_timeout) + QUEUE_AND_RESULT_GRACE
    )
    return min(requested, ceiling), "repository_ci" if ci_timeout else "default"


def start_wait(state, identity, budget, basis, wall, monotonic, *, new_round=False, extend=0):
    """Soft repair budgets can restart; a user's hard deadline survives every source round."""
    saved = state.get("watch")
    if saved is not None and not isinstance(saved, dict):
        raise ValueError("invalid watch checkpoint")
    hard_deadline, previous_remaining = None, None
    if saved:
        required = ("deadline_at", "remaining_seconds", "saved_monotonic", "budget_seconds")
        if any(
            isinstance(saved.get(key), bool) or not isinstance(saved.get(key), (float, int))
            or not math.isfinite(saved[key]) for key in required
        ) or saved["remaining_seconds"] < 0 or saved["budget_seconds"] <= 0:
            raise ValueError("invalid saved wait budget")
        elapsed = max(0, monotonic - saved["saved_monotonic"])
        previous_remaining = max(0, min(
            saved["deadline_at"] - wall, saved["remaining_seconds"] - elapsed
        ))
        hard_deadline = saved.get("hard_deadline_at")
        if hard_deadline is None and saved.get("basis") == "explicit":
            hard_deadline = saved["deadline_at"]
        if hard_deadline is not None and (
            isinstance(hard_deadline, bool) or not isinstance(hard_deadline, (float, int))
            or not math.isfinite(hard_deadline)
        ):
            raise ValueError("invalid hard deadline")
    if new_round:
        if not saved or saved.get("identity", {}).get("head") == identity["head"]:
            raise ValueError("a new round requires a verified changed source SHA")
        if saved.get("identity", {}).get("url") != identity["url"]:
            raise ValueError("a new round cannot replace the recorded PR")
        history = state.setdefault("watch_history", [])
        if not isinstance(history, list):
            raise ValueError("invalid watch history")
        history.append(saved)
        saved = None
    elif saved and saved.get("identity") != identity:
        raise ValueError("watch scope changed; preserve the checkpoint and verify a new source round")
    if saved is None:
        if extend and not new_round:
            raise ValueError("an extension requires an existing wait checkpoint")
        remaining = seconds(budget)
        if hard_deadline is not None:
            remaining = min(remaining, max(0, hard_deadline - wall), previous_remaining)
        saved = {
            "identity": identity, "budget_seconds": seconds(budget), "basis": basis,
            "started_at": wall, "deadline_at": wall + remaining,
            "remaining_seconds": remaining, "saved_monotonic": monotonic,
        }
        state["watch"] = saved
    else:
        remaining = previous_remaining
    if basis == "explicit":
        # A resumed smaller user cap may shorten the remaining wait; a larger flag
        # never grants an extension. --extend-seconds is the sole extension path.
        limit = seconds(budget)
        if hard_deadline is None:
            hard_deadline = min(saved["deadline_at"], wall + limit)
        elif limit < remaining:
            hard_deadline = min(hard_deadline, wall + limit)
        remaining = min(remaining, limit)
        saved["last_explicit_limit_seconds"] = budget
    if extend:
        extension = seconds(extend)
        remaining += extension
        saved["budget_seconds"] += extension
        if hard_deadline is not None:
            hard_deadline = max(wall, hard_deadline) + extension
        saved["deadline_at"] = wall + remaining
        saved["extensions"] = saved.get("extensions", 0) + 1
    if hard_deadline is not None:
        saved["hard_deadline_at"] = hard_deadline
        remaining = min(remaining, max(0, hard_deadline - wall))
        saved["deadline_at"] = min(saved["deadline_at"], hard_deadline)
    # Keep the original wall deadline during ordinary resumes. Rewriting it after
    # a clock rollback would charge the same rollback again when the clock recovers.
    saved.update(remaining_seconds=remaining, saved_monotonic=monotonic)
    return monotonic + remaining


def checkpoint_wait(state, deadline, monotonic):
    watch = state["watch"]
    watch.update(
        remaining_seconds=max(0, deadline - monotonic), saved_monotonic=monotonic,
    )
