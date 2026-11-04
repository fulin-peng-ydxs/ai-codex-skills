#!/usr/bin/env python3
"""Classify command text against JSON globs; never execute or authorize it."""

import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import re
import shlex


EXIT_CODES = {"allow": 0, "ask": 2, "deny": 3}
FIELDS = {"version", "targets", "approval_ref", "default", "deny", "ask", "allow"}
SCENARIO_FIELDS = {"version", "targets", "approval_ref", "deny", "scenarios"}
OPERATORS = set(";&|<>()")
WRAPPERS = {
    "ssh", "scp", "sftp", "sudo", "doas", "su", "env", "sh", "bash", "dash",
    "zsh", "fish", "busybox", "perl", "ruby", "node", "awk", "gawk", "mawk",
    "sed", "xargs", "find", "timeout", "nice", "nohup", "watch", "eval", "exec",
    "command", "source", ".",
}


def tokens(text):
    """Parse only literal argv; shell evaluation must receive separate review."""
    if not isinstance(text, str) or any(c in text for c in "\n\r\0$`"):
        raise ValueError("unsupported shell syntax")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    result = list(lexer)
    if not result or any(token and set(token) <= OPERATORS for token in result):
        raise ValueError("unsupported shell syntax")
    return result


def choices(part):
    """New-format alternatives occupy one complete argv slot, never shell code."""
    if part.startswith("{") and not part.startswith("{{") and "," in part:
        if not part.endswith("}") or any(c in part[1:-1] for c in "{}"):
            raise ValueError("invalid alternatives")
        result = part[1:-1].split(",")
        if any(not item or item == "**" for item in result):
            raise ValueError("invalid alternatives")
        return result
    return [part]


def matches(pattern, argv, alternatives=False):
    """A glob stays inside one argument; a standalone ** spans arguments."""
    row = [True] + [False] * len(argv)
    for part in pattern:
        if part == "**":
            current = [row[0]]
            for index in range(1, len(row)):
                current.append(row[index] or current[index - 1])
        else:
            options = choices(part) if alternatives else [part]
            current = [False] + [
                row[index - 1] and any(fnmatchcase(argument, option) for option in options)
                for index, argument in enumerate(argv, 1)
            ]
        row = current
    return row[-1]


def has_shell_expansion(command):
    """Keep quoted literal formats usable; do not guess unquoted expansions."""
    quote = None
    escaped = False
    for character in command:
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif character in "\"'":
            if quote == character:
                quote = None
            elif quote is None:
                quote = character
        elif quote is None and character in "*?[{}~#":
            return True
    return False


def validate(policy):
    """Reject incomplete/unknown fields instead of silently ignoring a rule."""
    if not isinstance(policy, dict) or set(policy) not in (FIELDS, SCENARIO_FIELDS):
        raise ValueError("invalid policy fields")
    if type(policy["version"]) is not int or policy["version"] < 1:
        raise ValueError("invalid version")
    approval = policy["approval_ref"]
    if approval is not None and (not isinstance(approval, str) or not approval.strip()):
        raise ValueError("invalid approval reference")
    if not isinstance(policy["targets"], list):
        raise ValueError("invalid targets")
    for target in policy["targets"]:
        if not isinstance(target, dict) or set(target) != {"server_id", "user"}:
            raise ValueError("invalid target fields")
        if any(not isinstance(v, str) or not v.strip() for v in target.values()):
            raise ValueError("invalid target value")
    def parse_rules(value, alternatives=False):
        if not isinstance(value, list):
            raise ValueError("rules must be lists")
        parsed = [(pattern, tokens(pattern)) for pattern in value]
        if alternatives:
            for _, parts in parsed:
                for part in parts:
                    choices(part)
        return parsed

    if "scenarios" in policy:
        rules = {"deny": parse_rules(policy["deny"], True), "scenarios": []}
        if not isinstance(policy["scenarios"], list) or not policy["scenarios"]:
            raise ValueError("invalid scenarios")
        names, prefixes = set(), set()
        for scenario in policy["scenarios"]:
            if not isinstance(scenario, dict) or scenario.get("default") not in ("ask", "allow"):
                raise ValueError("invalid scenario mode")
            exception = "ask" if scenario["default"] == "allow" else "allow"
            if set(scenario) != {"name", "prefix", "default", exception}:
                raise ValueError("a scenario has exactly one exception list")
            name, prefix = scenario["name"], scenario["prefix"]
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError("invalid scenario name")
            if not isinstance(prefix, str):
                raise ValueError("invalid scenario prefix")
            argv = tokens(prefix) if prefix else []
            if any(any(c in part for c in "*?[]{}") for part in argv) or tuple(argv) in prefixes:
                raise ValueError("scenario prefixes must be unique literal argv")
            names.add(name)
            prefixes.add(tuple(argv))
            rules["scenarios"].append({
                "name": name, "prefix": argv, "default": scenario["default"],
                "exception": exception, "rules": parse_rules(scenario[exception], True),
            })
        return rules

    # Existing project policies keep their original default-ask semantics.
    if policy["default"] != "ask":
        raise ValueError("legacy default must be ask")
    rules = {}
    for category in ("deny", "ask", "allow"):
        rules[category] = parse_rules(policy[category])
    return rules


def classify(policy, server_id, user, command):
    """Return a decision, not a claim about trusted approval or server state."""
    report = {"decision": "ask", "reason": "invalid-policy", "pattern": None, "policy_version": None}
    try:
        rules = validate(policy)
    except ValueError:
        return report
    report["policy_version"] = policy["version"]
    if {"server_id": server_id, "user": user} not in policy["targets"]:
        return dict(report, reason="target-not-covered")
    try:
        argv = tokens(command)
    except ValueError:
        return dict(report, reason="unsupported-shell")
    scoped = "scenarios" in rules
    for category in (("deny",) if scoped else ("deny", "ask")):
        for pattern, parsed in rules[category]:
            if matches(parsed, argv, alternatives=scoped):
                return dict(report, decision=category, reason=category + "-pattern", pattern=pattern)
    # Static argv matching cannot resolve shell pathname expansion safely.
    if has_shell_expansion(command):
        return dict(report, reason="shell-expansion")
    executable = Path(argv[0]).name
    if (
        executable in WRAPPERS or "=" in argv[0]
        or re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", executable)
        or executable.endswith((".sh", ".py", ".pl", ".rb", ".js"))
    ):
        return dict(report, reason="wrapped-command")
    if scoped:
        candidates = [scenario for scenario in rules["scenarios"]
                      if argv[:len(scenario["prefix"])] == scenario["prefix"]]
        if not candidates:
            return dict(report, reason="scenario-not-covered")
        scenario = max(candidates, key=lambda item: len(item["prefix"]))
        report.update(scenario=scenario["name"], mode=scenario["default"])
        suffix = argv[len(scenario["prefix"]):]
        decision, reason, pattern = scenario["default"], "scenario-default", None
        for candidate, parsed in scenario["rules"]:
            if matches(parsed, suffix, alternatives=True):
                decision, reason, pattern = scenario["exception"], "scenario-exception", candidate
                break
        if decision == "allow" and not policy["approval_ref"]:
            return dict(report, reason="unapproved-policy", pattern=pattern)
        return dict(report, decision=decision, reason=reason, pattern=pattern)
    for pattern, parsed in rules["allow"]:
        if matches(parsed, argv):
            reason = "allow-pattern" if policy["approval_ref"] else "unapproved-policy"
            return dict(report, decision="allow" if policy["approval_ref"] else "ask", reason=reason, pattern=pattern)
    return dict(report, reason="unmatched")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        policy = None
    report = classify(policy, args.server_id, args.user, args.command)
    print(json.dumps(report, ensure_ascii=False))
    return EXIT_CODES[report["decision"]]


if __name__ == "__main__":
    raise SystemExit(main())
