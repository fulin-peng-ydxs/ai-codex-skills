#!/usr/bin/env python3
import argparse
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MANAGED_STDIO_KEYS = (
    "args",
    "env",
    "env_vars",
    "cwd",
    "experimental_environment",
)


@dataclass
class Candidate:
    name: str
    command: str
    source: str
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class Registration:
    name: str
    command: str
    settings: dict[str, Any] = field(default_factory=dict)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def normalize_command(command: str, base: Path) -> str:
    expanded = os.path.expandvars(os.path.expanduser(command))
    path = Path(expanded)
    if path.is_absolute():
        return str(path.resolve())
    if expanded.startswith(".") or os.sep in expanded:
        return str((base / path).resolve())
    return expanded


def command_identity(command: str) -> str:
    expanded = os.path.expanduser(command)
    if os.sep in expanded or Path(expanded).is_absolute():
        return str(Path(expanded).resolve())
    return expanded


def normalize_string_map(value: Any, field_name: str, server_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{server_name}.{field_name} 必须是对象")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"{server_name}.{field_name} 的键和值必须是字符串或标量")
        normalized[key] = str(item)
    return normalized


def normalize_string_list(value: Any, field_name: str, server_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{server_name}.{field_name} 必须是字符串数组")
    return value


def candidate_settings(cfg: dict[str, Any], project: Path, server_name: str) -> dict[str, Any]:
    settings: dict[str, Any] = {}

    args = normalize_string_list(cfg.get("args"), "args", server_name)
    if args:
        settings["args"] = args

    env = normalize_string_map(cfg.get("env"), "env", server_name)
    if env:
        settings["env"] = env

    env_vars = cfg.get("env_vars")
    if env_vars is not None:
        if not isinstance(env_vars, list):
            raise ValueError(f"{server_name}.env_vars 必须是数组")
        settings["env_vars"] = env_vars

    cwd = cfg.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str):
            raise ValueError(f"{server_name}.cwd 必须是字符串")
        cwd_path = Path(cwd).expanduser()
        settings["cwd"] = str(cwd_path.resolve() if cwd_path.is_absolute() else (project / cwd_path).resolve())

    experimental_environment = cfg.get("experimental_environment")
    if experimental_environment is not None:
        if not isinstance(experimental_environment, str):
            raise ValueError(f"{server_name}.experimental_environment 必须是字符串")
        settings["experimental_environment"] = experimental_environment

    return settings


def discover_candidates(project: Path) -> list[Candidate]:
    # A shared launcher (npx/python/etc.) is not a service identity.
    candidates: list[Candidate] = []
    mcp_json = project / ".mcp.json"
    if mcp_json.exists():
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        mcp_servers = data.get("mcpServers", {})
        if not isinstance(mcp_servers, dict):
            raise ValueError(".mcp.json 的 mcpServers 必须是对象")
        for name, cfg in mcp_servers.items():
            if not isinstance(cfg, dict):
                raise ValueError(f"{name} 的 MCP 配置必须是对象")
            command = cfg.get("command")
            if not command:
                continue
            if not isinstance(command, str):
                raise ValueError(f"{name}.command 必须是字符串")
            candidate = Candidate(
                name=name,
                command=normalize_command(command, project),
                source=".mcp.json",
                settings=candidate_settings(cfg, project, name),
            )
            candidates.append(candidate)

    mcp_dir = project / ".codex-mcp"
    if mcp_dir.exists():
        for run_sh in sorted(mcp_dir.glob("*/run.sh")):
            command = str(run_sh.resolve())
            identity = command_identity(command)
            if not any(command_identity(item.command) == identity for item in candidates):
                name = f"{project.name}-{run_sh.parent.name}".replace("_", "-")
                candidates.append(Candidate(name=name, command=command, source=".codex-mcp"))

    if len({item.name for item in candidates}) != len(candidates):
        raise ValueError("项目候选服务名称冲突，请在 .mcp.json 中为启动入口指定不同名称")
    return sorted(candidates, key=lambda candidate: candidate.name)


def parse_registrations(config_text: str) -> dict[str, Registration]:
    data = tomllib.loads(config_text)
    raw_servers = data.get("mcp_servers", {})
    if not isinstance(raw_servers, dict):
        return {}

    registrations: dict[str, Registration] = {}
    for name, cfg in raw_servers.items():
        if not isinstance(cfg, dict):
            continue
        command = cfg.get("command")
        if not isinstance(command, str):
            # Reserve HTTP/other registration names without treating them as stdio.
            registrations[name] = Registration(name=name, command="", settings=dict(cfg))
            continue
        settings = {key: value for key, value in cfg.items() if key not in {"command", "url"}}
        registrations[name] = Registration(
            name=name,
            command=normalize_command(command, Path.cwd()),
            settings=settings,
        )
    return registrations


def unique_name(preferred: str, project_name: str, registrations: set[str]) -> str:
    clean = preferred
    if clean not in registrations:
        return clean
    prefixed = f"{project_name}-{clean}"
    if prefixed not in registrations:
        return prefixed
    index = 2
    while f"{prefixed}-{index}" in registrations:
        index += 1
    return f"{prefixed}-{index}"


def merge_candidate(existing: Registration, candidate: Candidate) -> Registration:
    settings = dict(existing.settings)
    # .mcp.json 只接管 STDIO 启动字段，避免覆盖 Codex 独有的启停、超时和审批策略。
    for key in MANAGED_STDIO_KEYS:
        settings.pop(key, None)
    settings.update(candidate.settings)
    return Registration(name=existing.name, command=candidate.command, settings=settings)


def same_launch(candidate: Candidate, registration: Registration) -> bool:
    """Use the full launch description only to disambiguate known name aliases."""
    defaults = {"args": [], "env": {}, "env_vars": []}
    return (command_identity(candidate.command) == command_identity(registration.command)
            and all(candidate.settings.get(key, defaults.get(key))
                    == registration.settings.get(key, defaults.get(key))
                    for key in MANAGED_STDIO_KEYS))


def match_registrations(candidates: list[Candidate], registrations: dict[str, Registration],
                        project_name: str) -> dict[str, str]:
    """Resolve an injective mapping against the original snapshot, before writes.

    Exact declared names take precedence. Legacy underscore normalization and
    generated project prefixes are aliases, not proof of ownership when shared.
    Ambiguous aliases fail closed rather than merging candidates or duplicating
    an existing service under a new name.
    """
    matches = {}
    for candidate in candidates:
        named = registrations.get(candidate.name)
        if named and command_identity(named.command) == command_identity(candidate.command):
            matches[candidate.name] = named.name
    claimed = set(matches.values())
    declared = {item.name for item in candidates}
    pending = {item.name: item for item in candidates if item.name not in matches}
    options = {}
    blocked_legacy = set()
    for name, candidate in pending.items():
        legacy = name.replace("_", "-")
        prefixes = {f"{project_name}-{name}", f"{project_name}-{name}".replace("_", "-")}
        options[name] = set()
        for key, registration in registrations.items():
            if command_identity(candidate.command) != command_identity(registration.command):
                continue
            if legacy != name and key == legacy and key in claimed:
                blocked_legacy.add(name)
            alias = key == legacy or any(
                re.fullmatch(re.escape(prefix) + r"(?:-(?:[2-9]|[1-9]\d+))?", key)
                for prefix in prefixes
            )
            if alias and key not in claimed and key not in declared:
                options[name].add(key)

    # Full launch equality can establish which candidate owns a shared alias.
    for key in set().union(*options.values()) if options else set():
        owners = [name for name in options if key in options[name]]
        exact = [name for name in owners if same_launch(pending[name], registrations[key])]
        if len(exact) == 1:
            for name in set(owners) - set(exact):
                options[name].discard(key)
    for name, choices in options.items():
        exact = {key for key in choices if same_launch(pending[name], registrations[key])}
        if exact:
            options[name] = exact
        if not options[name] and name in blocked_legacy:
            raise ValueError(f"历史注册名称归属冲突：{name}；请先明确服务名称")

    unresolved = {name: choices for name, choices in options.items() if choices}
    while unresolved:
        singles = {name: next(iter(choices)) for name, choices in unresolved.items() if len(choices) == 1}
        if not singles or len(set(singles.values())) != len(singles):
            raise ValueError("MCP 注册别名归属不唯一，请明确冲突服务名称后重试")
        matches.update(singles)
        used = set(singles.values())
        for name in singles:
            del unresolved[name]
        for choices in unresolved.values():
            choices.difference_update(used)
            if not choices:
                raise ValueError("多个 MCP 候选竞争同一注册，请明确服务名称后重试")
    return matches


def plan_registrations(
    candidates: list[Candidate],
    registrations: dict[str, Registration],
    project_name: str,
) -> tuple[list[Registration], list[Registration], list[Registration]]:
    additions: list[Registration] = []
    updates: list[Registration] = []
    project_regs: list[Registration] = []
    candidate_names = {item.name for item in candidates}
    if len(candidate_names) != len(candidates):
        raise ValueError("MCP 候选名称重复")
    matches = match_registrations(candidates, registrations, project_name)
    # Reserve every candidate's generated base, not just its declared name.
    bases = {f"{project_name}-{name}" for name in candidate_names}
    reserved = candidate_names | bases | {name.replace("_", "-") for name in candidate_names | bases}
    planned = dict(registrations)

    for candidate in candidates:
        existing = registrations[matches[candidate.name]] if candidate.name in matches else None
        if existing is not None:
            if candidate.source == ".mcp.json":
                desired = merge_candidate(existing, candidate)
                if desired.command != existing.command or desired.settings != existing.settings:
                    planned[existing.name] = desired
                    updates.append(desired)
            project_regs.append(planned[existing.name])
            continue

        own_names = {candidate.name}
        if f"{project_name}-{candidate.name}" not in candidate_names:
            own_names.add(f"{project_name}-{candidate.name}")
        unavailable = (reserved - own_names) | set(planned)
        name = unique_name(candidate.name, project_name, unavailable)
        registration = Registration(name=name, command=candidate.command, settings=dict(candidate.settings))
        planned[name] = registration
        additions.append(registration)
        project_regs.append(registration)

    if (len({item.name for item in project_regs}) != len(candidates)
            or {item.name for item in additions} & {item.name for item in updates}):
        raise ValueError("MCP 注册计划不是一对一映射，未写入配置")
    registrations.update(planned)
    return additions, updates, project_regs


def toml_key(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else json.dumps(value, ensure_ascii=False)


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_key(str(key))} = {toml_value(item)}" for key, item in value.items()) + " }"
    raise TypeError(f"不支持写入 TOML 的值类型：{type(value).__name__}")


def render_registration(registration: Registration) -> str:
    name = toml_key(registration.name)
    lines = [
        f"[mcp_servers.{name}]",
        f"command = {toml_value(registration.command)}",
    ]
    for key, value in registration.settings.items():
        if key == "env":
            continue
        lines.append(f"{key} = {toml_value(value)}")

    env = registration.settings.get("env")
    if isinstance(env, dict) and env:
        lines.extend(["", f"[mcp_servers.{name}.env]"])
        lines.extend(f"{toml_key(str(key))} = {toml_value(value)}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def parse_mcp_header(line: str) -> tuple[str | None, bool]:
    stripped = line.strip()
    if not stripped.startswith("[") or stripped.startswith("[["):
        return None, False
    try:
        parsed = tomllib.loads(f"{stripped}\n__sync_project_mcp_marker__ = true\n")
    except tomllib.TOMLDecodeError:
        return None, False
    servers = parsed.get("mcp_servers")
    if not isinstance(servers, dict) or len(servers) != 1:
        return None, False
    name, value = next(iter(servers.items()))
    is_main = isinstance(value, dict) and value.get("__sync_project_mcp_marker__") is True
    return name, is_main


def registration_span(lines: list[str], name: str) -> tuple[int, int]:
    start = -1
    for index, line in enumerate(lines):
        owner, is_main = parse_mcp_header(line)
        if owner == name and is_main:
            start = index
            break
    if start < 0:
        raise ValueError(f"无法在 config.toml 中定位 MCP 配置块：{name}")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        owner, _ = parse_mcp_header(lines[index])
        if lines[index].lstrip().startswith("[") and owner != name:
            end = index
            break
    return start, end


def write_registrations(
    config_path: Path,
    config_text: str,
    additions: list[Registration],
    updates: list[Registration],
    dry_run: bool,
) -> None:
    if (not additions and not updates) or dry_run:
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = config_path.with_suffix(config_path.suffix + f".bak-sync-project-mcp-{timestamp}")
    shutil.copy2(config_path, backup_path)

    lines = config_text.splitlines(keepends=True)
    edits: list[tuple[int, int, str]] = []
    for registration in updates:
        start, end = registration_span(lines, registration.name)
        edits.append((start, end, render_registration(registration)))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]

    updated_text = "".join(lines)
    if additions:
        separator = "\n" if updated_text and not updated_text.endswith("\n\n") else ""
        updated_text += separator + "\n".join(render_registration(item) for item in additions)
    config_path.write_text(updated_text, encoding="utf-8")


def json_rpc_request(proc: subprocess.Popen, request: dict, timeout_seconds: float) -> dict:
    line = json.dumps(request, separators=(",", ":")) + "\n"
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(line)
    proc.stdin.flush()

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"进程已退出，退出码：{proc.returncode}")
        ready, _, _ = select.select([proc.stdout], [], [], max(0.0, min(0.1, deadline - time.time())))
        if ready:
            response = proc.stdout.readline()
            if response:
                return json.loads(response)
    raise TimeoutError(f"{timeout_seconds}s 后超时")


def validate_registration(registration: Registration, timeout_seconds: float) -> tuple[bool, str]:
    executable = registration.command
    if os.sep in executable or Path(executable).is_absolute():
        if not Path(executable).exists():
            return False, f"command does not exist: {executable}"
    elif shutil.which(executable) is None:
        return False, f"command not found in PATH: {executable}"

    args = registration.settings.get("args", [])
    env = os.environ.copy()
    configured_env = registration.settings.get("env", {})
    if isinstance(configured_env, dict):
        env.update({str(key): str(value) for key, value in configured_env.items()})
    cwd = registration.settings.get("cwd")
    if cwd is None and (os.sep in executable or Path(executable).is_absolute()):
        cwd = str(Path(executable).parent)

    proc = None
    stage = "启动"
    try:
        # Untrusted service diagnostics can contain credentials. Discard stderr
        # rather than attempting an incomplete pattern-based secret scrubber.
        proc = subprocess.Popen(
            [executable, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            env=env,
        )
        stage = "initialize"
        init_response = json_rpc_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "config-project-mcp-sync", "version": "0.2.0"},
                },
            },
            timeout_seconds,
        )
        if "error" in init_response:
            return False, rpc_error_summary(stage, init_response["error"])

        stage = "tools/list"
        tools_response = json_rpc_request(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout_seconds,
        )
        if "error" in tools_response:
            return False, rpc_error_summary(stage, tools_response["error"])
        tools = tools_response.get("result", {}).get("tools", [])
        return True, f"{len(tools)} 个工具"
    except Exception as exc:
        # Exception text may embed malformed responses, args, URLs or env values.
        if isinstance(exc, TimeoutError):
            reason = f"请求超时（{timeout_seconds}s）"
        elif isinstance(exc, OSError):
            reason = f"系统调用失败（errno={exc.errno}）"
        elif isinstance(exc, (ValueError, TypeError, AttributeError)):
            reason = "服务响应格式无效"
        elif proc is not None and proc.poll() is not None:
            reason = f"服务已退出（退出码={proc.returncode}）"
        else:
            reason = "协议交互失败"
        return False, f"{stage}：{reason}；服务错误正文与 stderr 不回显"
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for stream in (proc.stdin, proc.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        # Closing buffered stdin may retry a failed flush after
                        # the peer closed its pipe. Preserve the primary result
                        # and still close the other stream / validate next service.
                        pass


def rpc_error_summary(stage: str, error: Any) -> str:
    """Expose only a numeric protocol code, never arbitrary remote error fields."""
    code = error.get("code") if isinstance(error, dict) else None
    suffix = f"（错误码={code}）" if type(code) is int else ""
    return f"{stage}：服务返回错误{suffix}；错误正文已省略"


def parameter_summary(registration: Registration) -> str:
    args_count = len(registration.settings.get("args", []))
    env_count = len(registration.settings.get("env", {}))
    env_vars_count = len(registration.settings.get("env_vars", []))
    cwd = "，含 cwd" if registration.settings.get("cwd") else ""
    return f"args {args_count} 项，env {env_count} 项，env_vars {env_vars_count} 项{cwd}"


def main() -> int:
    parser = argparse.ArgumentParser(description="同步并验证当前项目的本地 Codex MCP 服务。")
    parser.add_argument("--project", default=os.getcwd(), help="包含 .codex-mcp 或 .mcp.json 的项目根目录。")
    parser.add_argument("--config", default=str(codex_home() / "config.toml"), help="Codex config.toml 路径。")
    parser.add_argument("--dry-run", action="store_true", help="只报告将要新增或更新的注册项，不写入 config.toml。")
    parser.add_argument("--no-validate", action="store_true", help="不启动 MCP 服务做验证。")
    parser.add_argument("--timeout", type=float, default=8.0, help="每次 JSON-RPC 请求的超时时间，单位秒。")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"未找到 Codex 配置：{config_path}", file=sys.stderr)
        return 2

    try:
        candidates = discover_candidates(project)
        if not candidates:
            print(f"未在项目下发现 MCP 候选项：{project}")
            return 0

        config_text = config_path.read_text(encoding="utf-8")
        registrations = parse_registrations(config_text)
        additions, updates, project_regs = plan_registrations(candidates, registrations, project.name)
        write_registrations(config_path, config_text, additions, updates, args.dry_run)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"同步 MCP 配置失败：{exc}", file=sys.stderr)
        return 2

    print(f"项目：{project}")
    print(f"Codex 配置：{config_path}")
    print("")
    if additions:
        action = "将注册" if args.dry_run else "已注册"
        print(f"{action} {len(additions)} 个缺失的 MCP 服务：")
        for registration in additions:
            print(f"- {registration.name}: {registration.command}（{parameter_summary(registration)}）")
    if updates:
        action = "将更新" if args.dry_run else "已更新"
        print(f"{action} {len(updates)} 个参数不一致的 MCP 服务：")
        for registration in updates:
            print(f"- {registration.name}: {registration.command}（{parameter_summary(registration)}）")
    if not additions and not updates:
        print("没有需要注册或更新的 MCP。")

    added_names = {item.name for item in additions}
    updated_names = {item.name for item in updates}

    print("")
    print("当前项目 MCP 注册列表：")
    for registration in project_regs:
        if registration.name in added_names:
            marker = "新增"
        elif registration.name in updated_names:
            marker = "更新"
        else:
            marker = "已存在"
        print(f"- {registration.name}: {registration.command} [{marker}]（{parameter_summary(registration)}）")

    if args.no_validate:
        return 0

    print("")
    print("验证结果：")
    failures = 0
    for registration in project_regs:
        ok, message = validate_registration(registration, args.timeout)
        status = "通过" if ok else "失败"
        print(f"- {registration.name}: {status} ({message})")
        if not ok:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
