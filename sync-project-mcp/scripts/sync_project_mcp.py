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
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Candidate:
    name: str
    command: Path
    source: str


@dataclass
class Registration:
    name: str
    command: Path


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def resolve_command(command: str, project: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(command))
    path = Path(expanded)
    if not path.is_absolute():
        path = project / path
    return path.resolve()


def discover_candidates(project: Path) -> list[Candidate]:
    by_command: dict[Path, Candidate] = {}
    mcp_json = project / ".mcp.json"
    if mcp_json.exists():
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        for name, cfg in data.get("mcpServers", {}).items():
            command = cfg.get("command")
            if not command:
                continue
            candidate = Candidate(name=name, command=resolve_command(command, project), source=".mcp.json")
            by_command[candidate.command] = candidate

    mcp_dir = project / ".codex-mcp"
    if mcp_dir.exists():
        for run_sh in sorted(mcp_dir.glob("*/run.sh")):
            command = run_sh.resolve()
            if command not in by_command:
                name = f"{project.name}-{run_sh.parent.name}".replace("_", "-")
                by_command[command] = Candidate(name=name, command=command, source=".codex-mcp")

    return sorted(by_command.values(), key=lambda c: c.name)


def parse_registrations(config_text: str) -> dict[str, Registration]:
    registrations: dict[str, Registration] = {}
    section_re = re.compile(r"^\[mcp_servers\.([^\]]+)\]\s*$")
    command_re = re.compile(r'^\s*command\s*=\s*"([^"]+)"\s*$')
    current_name: str | None = None

    for line in config_text.splitlines():
        section = section_re.match(line)
        if section:
            current_name = section.group(1)
            continue
        if line.startswith("["):
            current_name = None
            continue
        if current_name:
            command_match = command_re.match(line)
            if command_match:
                registrations[current_name] = Registration(
                    name=current_name,
                    command=Path(os.path.expanduser(command_match.group(1))).resolve(),
                )
    return registrations


def unique_name(preferred: str, project_name: str, registrations: dict[str, Registration]) -> str:
    clean = preferred.replace("_", "-")
    if clean not in registrations:
        return clean
    prefixed = f"{project_name}-{clean}".replace("_", "-")
    if prefixed not in registrations:
        return prefixed
    index = 2
    while f"{prefixed}-{index}" in registrations:
        index += 1
    return f"{prefixed}-{index}"


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def append_registrations(
    config_path: Path,
    config_text: str,
    candidates: list[Candidate],
    registrations: dict[str, Registration],
    project_name: str,
    dry_run: bool,
) -> list[Registration]:
    registered_commands = {registration.command for registration in registrations.values()}
    additions: list[Registration] = []

    for candidate in candidates:
        if candidate.command in registered_commands:
            continue
        name = unique_name(candidate.name, project_name, registrations)
        registration = Registration(name=name, command=candidate.command)
        registrations[name] = registration
        registered_commands.add(candidate.command)
        additions.append(registration)

    if additions and not dry_run:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = config_path.with_suffix(config_path.suffix + f".bak-sync-project-mcp-{timestamp}")
        shutil.copy2(config_path, backup_path)
        blocks = []
        for registration in additions:
            blocks.append(
                "\n"
                f"[mcp_servers.{registration.name}]\n"
                f"command = {toml_string(str(registration.command))}\n"
            )
        separator = "" if config_text.endswith("\n") else "\n"
        config_path.write_text(config_text + separator + "".join(blocks), encoding="utf-8")

    return additions


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
    if not registration.command.exists():
        return False, f"command does not exist: {registration.command}"
    proc = subprocess.Popen(
        [str(registration.command)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(registration.command.parent),
    )
    try:
        init_response = json_rpc_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "sync-project-mcp", "version": "0.1.0"},
                },
            },
            timeout_seconds,
        )
        if "error" in init_response:
            return False, f"initialize 错误：{init_response['error']}"

        tools_response = json_rpc_request(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout_seconds,
        )
        if "error" in tools_response:
            return False, f"tools/list 错误：{tools_response['error']}"
        tools = tools_response.get("result", {}).get("tools", [])
        return True, f"{len(tools)} 个工具"
    except Exception as exc:
        stderr = ""
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
        if proc.stderr is not None:
            try:
                stderr = proc.stderr.read(2000)
            except Exception:
                stderr = ""
        details = str(exc)
        if stderr.strip():
            details = f"{details}；stderr：{stderr.strip()}"
        return False, details
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="注册并验证当前项目的本地 Codex MCP 服务。")
    parser.add_argument("--project", default=os.getcwd(), help="包含 .codex-mcp 或 .mcp.json 的项目根目录。")
    parser.add_argument("--config", default=str(codex_home() / "config.toml"), help="Codex config.toml 路径。")
    parser.add_argument("--dry-run", action="store_true", help="只报告将要新增的注册项，不写入 config.toml。")
    parser.add_argument("--no-validate", action="store_true", help="不启动 MCP 服务做验证。")
    parser.add_argument("--timeout", type=float, default=8.0, help="每次 JSON-RPC 请求的超时时间，单位秒。")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"未找到 Codex 配置：{config_path}", file=sys.stderr)
        return 2

    candidates = discover_candidates(project)
    if not candidates:
        print(f"未在项目下发现 MCP 候选项：{project}")
        return 0

    config_text = config_path.read_text(encoding="utf-8")
    registrations = parse_registrations(config_text)
    before = dict(registrations)
    additions = append_registrations(config_path, config_text, candidates, registrations, project.name, args.dry_run)

    by_command = {registration.command: registration for registration in registrations.values()}
    project_regs = [by_command[candidate.command] for candidate in candidates if candidate.command in by_command]

    print(f"项目：{project}")
    print(f"Codex 配置：{config_path}")
    print("")
    if additions:
        action = "将注册" if args.dry_run else "已注册"
        print(f"{action} {len(additions)} 个缺失的 MCP 服务：")
        for registration in additions:
            print(f"- {registration.name}: {registration.command}")
    else:
        print("没有需要注册的 MCP。")

    print("")
    print("当前项目 MCP 注册列表：")
    for registration in project_regs:
        marker = "新增" if registration.name in {item.name for item in additions} else "已存在"
        original = next((name for name, reg in before.items() if reg.command == registration.command), registration.name)
        display_name = registration.name if registration.name == original else f"{registration.name}（匹配已有注册 {original}）"
        print(f"- {display_name}: {registration.command} [{marker}]")

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
