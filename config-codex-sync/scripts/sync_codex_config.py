#!/usr/bin/env python3
"""Synchronize Codex user skills and collaboration instructions to Claude and Kimi."""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


STATE_FILE = ".codex-skill-sync.json"
RETIREMENTS = Path(__file__).resolve().parents[1] / "references/retired-skills.json"

CODEX_ONLY_SKILLS = {"automation-management", "config-codex-sync"}


IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".idea",
    ".obsidian",
    ".system",
    "__pycache__",
    "node_modules",
}

class SyncError(RuntimeError):
    """Raised when synchronization cannot continue safely."""


@dataclass
class Counts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def add(self, other: "Counts") -> None:
        self.created += other.created
        self.updated += other.updated
        self.unchanged += other.unchanged


def expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve(strict=False)


def default_root(primary_env: str, fallback: str, secondary_env: str | None = None) -> Path:
    value = os.environ.get(primary_env)
    if value is None and secondary_env:
        value = os.environ.get(secondary_env)
    return expand_path(value or fallback)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 Codex 全局技能和协作说明更新到 Claude、Kimi 用户目录。"
    )
    parser.add_argument(
        "--target",
        choices=("all", "claude", "kimi"),
        default="all",
        help="同步目标，默认 all。",
    )
    parser.add_argument(
        "--codex-root",
        type=expand_path,
        default=default_root("CODEX_HOME", "~/.codex"),
        help="Codex 用户根目录。",
    )
    parser.add_argument(
        "--claude-root",
        type=expand_path,
        default=default_root("CLAUDE_CONFIG_DIR", "~/.claude", "CLAUDE_HOME"),
        help="Claude Code 用户根目录。",
    )
    parser.add_argument(
        "--kimi-root",
        type=expand_path,
        default=default_root("KIMI_CODE_HOME", "~/.agents"),
        help="Kimi Code 用户根目录。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只预览，不创建或更新任何文件。",
    )
    parser.add_argument(
        "--delete", action="store_true",
        help="按同步基线清理多余文件和已退役的受管技能；保留独有、修改冲突及排除项。",
    )
    parser.add_argument("--origin-root", type=expand_path, help="稳定的完整 Codex 根目录；使用临时适配源时必须指定。")
    parser.add_argument("--partial", action="store_true", help="仅同步所选技能，不据缺失推断整项退役。")
    return parser.parse_args()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_paths(source_root: Path, targets: list[tuple[str, Path]]) -> None:
    source_skills = source_root / "skills"
    source_agents = source_root / "AGENTS.md"
    if not source_skills.is_dir():
        raise SyncError(f"Codex skills 目录不存在：{source_skills}")
    if not source_agents.is_file():
        raise SyncError(f"Codex AGENTS.md 不存在：{source_agents}")

    for label, target_root in targets:
        if target_root == source_root:
            raise SyncError(f"{label} 根目录不能与 Codex 根目录相同：{target_root}")
        if is_relative_to(target_root, source_skills):
            raise SyncError(f"{label} 根目录不能位于 Codex skills 内部：{target_root}")
        if target_root.exists() and not target_root.is_dir():
            raise SyncError(f"{label} 根路径不是目录：{target_root}")
        target_skills = target_root / "skills"
        if target_skills.is_symlink():
            raise SyncError(f"目标 skills 不得为符号链接：{target_skills}")
        if is_relative_to(source_root, target_root) or is_relative_to(target_root, source_root):
            raise SyncError(f"源与目标不能互相嵌套：{source_root} -> {target_root}")
    for index, (_, left) in enumerate(targets):
        for _, right in targets[index + 1:]:
            if is_relative_to(left, right) or is_relative_to(right, left):
                raise SyncError(f"同步目标不能重合或互相嵌套：{left}、{right}")


def protected_entry(path: Path) -> bool:
    """Never delete hidden data, repository metadata, caches or symlink targets."""
    return path.name.startswith(".") or path.name in IGNORED_NAMES or path.suffix == ".pyc" or path.is_symlink()


def plan_deletions(source_skills: Path, target_skills: Path) -> list[Path]:
    """Build a postorder cleanup plan only inside matching, sync-eligible skills.

    Protected descendants keep their parent directories alive. Unrecognized
    top-level files and directories are not managed by this synchronizer.
    """
    if not target_skills.exists():
        return []
    sources, _ = discover_skills(source_skills)
    targets, _ = discover_skills(target_skills)
    source_names = {p.name for p in sources}
    plan: list[Path] = []

    def walk(source: Path, target: Path) -> bool:
        if protected_entry(target):
            return False
        present = source.exists() or source.is_symlink()
        if target.is_dir():
            removable = True
            for child in sorted(target.iterdir()):
                if not walk(source / child.name, child):
                    removable = False
            if not present and removable:
                plan.append(target)
                return True
            return False
        if not present and target.is_file():
            plan.append(target)
            return True
        return False

    for target in targets:
        source = source_skills / target.name
        # Target-only and source-excluded skills are never deletion candidates.
        if target.name not in source_names:
            continue
        walk(source, target)
    return plan


def apply_deletions(paths: list[Path]) -> None:
    """Remove only planned entries; rmdir refuses unexpected new descendants."""
    for path in paths:
        if protected_entry(path):
            raise SyncError(f"删除计划中的路径类型已变化：{path}")
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()


def tree_snapshot(path: Path, source: bool = False) -> dict[str, str]:
    """Hash regular files without following symlinks; include empty directories."""
    result = {}
    def walk(item: Path, key: str):
        if source and (item.name in IGNORED_NAMES or item.suffix == ".pyc"):
            return
        if item.is_symlink():
            result[key] = "link:" + os.readlink(item)
        elif item.is_dir():
            result[key] = "dir"
            for child in sorted(item.iterdir()):
                walk(child, child.name if key == "." else key + "/" + child.name)
        elif item.is_file():
            result[key] = "sha256:" + hashlib.sha256(item.read_bytes()).hexdigest()
        else:
            result[key] = "special"
    if path.exists() or path.is_symlink():
        walk(path, ".")
    return result


def validate_inventory(inventory: dict) -> None:
    """Treat persisted path data as untrusted, never as an arbitrary delete path."""
    if not isinstance(inventory, dict):
        raise SyncError("无效的技能管理清单")
    for name, snapshot in inventory.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", name):
            raise SyncError("清单技能名不合法")
        if not isinstance(snapshot, dict) or "." not in snapshot:
            raise SyncError("清单缺少技能根对象")
        for key, value in snapshot.items():
            if not isinstance(key, str) or (key != "." and ("\\" in key or any(part in ("", ".", "..") for part in key.split("/")))):
                raise SyncError("清单路径不合法")
            if not isinstance(value, str) or not (value in ("dir", "special") or value.startswith("link:") or re.fullmatch(r"sha256:[0-9a-f]{64}", value)):
                raise SyncError("清单哈希不合法")


def load_state(target: Path, origin: Path) -> dict:
    path = target / STATE_FILE
    if path.is_symlink():
        raise SyncError("管理清单不能是符号链接")
    if not path.exists():
        return {"schema_version": 1, "origin": str(origin), "managed": {}}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("origin") != str(origin):
        raise SyncError("管理清单版本或源身份不匹配；禁止重建基线绕过冲突")
    validate_inventory(data.get("managed"))
    return data


def write_state(target: Path, state: dict) -> None:
    target.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=".codex-skill-sync-", dir=target)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, target / STATE_FILE)
    finally:
        temporary.unlink(missing_ok=True)


def load_retirements() -> dict:
    data = json.loads(RETIREMENTS.read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("skills"), dict):
        raise SyncError("退役登记无效")
    for name, entry in data["skills"].items():
        if not isinstance(entry, dict) or not isinstance(entry.get("baselines"), list):
            raise SyncError("退役登记缺少基线")
        for baseline in entry["baselines"]:
            validate_inventory({name: baseline["snapshot"]})
    return data["skills"]


def managed_deletions(source: Path, target: Path, state: dict, retirements: dict, partial: bool, origin_skills: Path | None = None):
    """Use trusted ownership baselines; unknown or changed data never auto-deletes."""
    managed = state["managed"]
    paths, conflicts, retired, guards = [], [], set(), {}
    for path in plan_deletions(source, target):
        relative = path.relative_to(target)
        name = relative.parts[0]
        key = "/".join(relative.parts[1:]) or "."
        current = tree_snapshot(path).get(".")
        baseline = managed.get(name, {}).get(key)
        if current == "dir":
            # Only remove empty directories whose complete contents are approved.
            descendants = list(path.rglob("*"))
            if baseline == "dir" and all(child in paths for child in descendants):
                paths.append(path)
        elif baseline == current and current and current.startswith("sha256:"):
            paths.append(path)
            guards[path] = tree_snapshot(path)
        else:
            conflicts.append(f"{path}: 无同步基线或目标已修改，保留")
    if not partial:
        for name in sorted(set(managed) | set(retirements)):
            src, dest = source / name, target / name
            canonical = (origin_skills or source) / name
            if canonical.exists() or canonical.is_symlink():
                continue
            if src.exists() or src.is_symlink():
                continue
            if not dest.exists() and not dest.is_symlink():
                retired.add(name)
                continue
            if is_excluded_mcp_skill(dest) or is_codex_only_skill(dest):
                continue
            current = tree_snapshot(dest)
            baselines = [managed[name]] if name in managed else [x["snapshot"] for x in retirements[name]["baselines"]]
            protected = any(protected_entry(dest / key) for key in current if key != ".") or protected_entry(dest)
            if current not in baselines or protected or "special" in current.values():
                conflicts.append(f"{dest}: 退役副本与基线不一致或含受保护项，保留")
                continue
            guards[dest] = current
            paths.extend(sorted((dest / key for key in current if key != "."), key=lambda p: len(p.parts), reverse=True))
            paths.append(dest)
            retired.add(name)
    return paths, conflicts, retired, guards


def has_skill_frontmatter(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline().strip()
            if first != "---":
                return False
            fields: set[str] = set()
            for line in handle:
                stripped = line.strip()
                if stripped == "---":
                    break
                if ":" in stripped and not stripped.startswith("#"):
                    fields.add(stripped.split(":", 1)[0].strip())
            else:
                return False
        return {"name", "description"}.issubset(fields)
    except (OSError, UnicodeError):
        return False


def read_skill_frontmatter(path: Path) -> str:
    skill_file = path if path.is_file() else path / "SKILL.md"
    try:
        with skill_file.open("r", encoding="utf-8") as handle:
            if handle.readline().strip() != "---":
                return ""
            lines: list[str] = []
            for line in handle:
                if line.strip() == "---":
                    return "".join(lines)
                lines.append(line)
    except (OSError, UnicodeError):
        return ""
    return ""


def is_excluded_mcp_skill(path: Path) -> bool:
    """Return whether a skill is identified as MCP-related."""
    identity = f"{path.stem if path.is_file() else path.name}\n{read_skill_frontmatter(path)}"
    return "mcp" in identity.casefold()


def is_codex_only_skill(path: Path) -> bool:
    """Match registered Codex-only identities without excluding portable workflows."""
    name = path.stem if path.is_file() else path.name
    if name in CODEX_ONLY_SKILLS:
        return True
    match = re.search(r"^name:\s*['\"]?([a-z0-9-]+)['\"]?\s*$", read_skill_frontmatter(path), re.MULTILINE)
    return bool(match and match.group(1) in CODEX_ONLY_SKILLS)


def discover_skills(skills_root: Path) -> tuple[list[Path], list[Path]]:
    skills: list[Path] = []
    excluded_skills: list[Path] = []
    for entry in sorted(skills_root.iterdir(), key=lambda item: item.name):
        if entry.name.startswith(".") or entry.name in IGNORED_NAMES:
            continue
        is_skill = (
            entry.is_dir()
            and not entry.is_symlink()
            and (entry / "SKILL.md").is_file()
        ) or (
            entry.is_file()
            and entry.suffix.lower() == ".md"
            and has_skill_frontmatter(entry)
        )
        if not is_skill:
            continue
        if is_excluded_mcp_skill(entry) or is_codex_only_skill(entry):
            excluded_skills.append(entry)
        else:
            skills.append(entry)
    return skills, excluded_skills


def destination_kind_conflicts(source: Path, destination: Path) -> bool:
    if not destination.exists() and not destination.is_symlink():
        return False
    if source.is_symlink():
        return destination.is_dir() and not destination.is_symlink()
    if source.is_dir():
        return not destination.is_dir() or destination.is_symlink()
    return destination.is_dir() or destination.is_symlink()


def files_equal(source: Path, destination: Path) -> bool:
    return (
        destination.is_file()
        and not destination.is_symlink()
        and filecmp.cmp(source, destination, shallow=False)
        and stat.S_IMODE(source.stat().st_mode) == stat.S_IMODE(destination.stat().st_mode)
    )


def sync_entry(source: Path, destination: Path, dry_run: bool) -> Counts:
    if destination_kind_conflicts(source, destination):
        raise SyncError(f"路径类型冲突：{source} -> {destination}")

    if source.is_symlink():
        link_target = os.readlink(source)
        if destination.is_symlink() and os.readlink(destination) == link_target:
            return Counts(unchanged=1)
        existed = destination.exists() or destination.is_symlink()
        if not dry_run:
            if destination.is_symlink() or destination.is_file():
                destination.unlink()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(link_target, target_is_directory=source.is_dir())
        return Counts(updated=1) if existed else Counts(created=1)

    if source.is_dir():
        existed = destination.exists()
        if not dry_run:
            destination.mkdir(parents=True, exist_ok=True)
        counts = Counts(unchanged=1) if existed else Counts(created=1)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            if child.name in IGNORED_NAMES or child.suffix == ".pyc":
                continue
            counts.add(sync_entry(child, destination / child.name, dry_run))
        return counts

    if files_equal(source, destination):
        return Counts(unchanged=1)
    existed = destination.exists() or destination.is_symlink()
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)
    return Counts(updated=1) if existed else Counts(created=1)


def sync_document(source: Path, destination: Path, dry_run: bool) -> str:
    if destination.exists() and destination.is_dir():
        raise SyncError(f"文档目标是目录：{destination}")
    if files_equal(source, destination):
        return "未变化"
    status = "更新" if destination.exists() or destination.is_symlink() else "新增"
    if dry_run:
        return status

    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as target_handle, source.open("rb") as source_handle:
            shutil.copyfileobj(source_handle, target_handle)
        shutil.copymode(source, temporary_path)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return status


def selected_targets(args: argparse.Namespace) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    if args.target in ("all", "claude"):
        targets.append(("Claude", args.claude_root))
    if args.target in ("all", "kimi"):
        targets.append(("Kimi", args.kimi_root))
    return targets


def target_document_name(label: str) -> str:
    if label == "Claude":
        return "CLAUDE.md"
    return "AGENTS.md"


def main() -> int:
    args = parse_args()
    targets = selected_targets(args)
    try:
        validate_paths(args.codex_root, targets)
        origin = args.origin_root or args.codex_root
        if not (origin / "skills").is_dir():
            raise SyncError("完整源目录不存在")
        origin_skills, _ = discover_skills(origin / "skills")
        source_skills_root = args.codex_root / "skills"
        source_agents = args.codex_root / "AGENTS.md"
        skills, excluded_skills = discover_skills(source_skills_root)
        if not skills:
            raise SyncError(f"未发现可同步技能：{source_skills_root}")

        names = {p.name for p in skills}
        origin_names = {p.name for p in origin_skills}
        if (not args.partial and names != origin_names) or not names <= origin_names:
            raise SyncError("适配源集合与完整源不一致；局部同步必须使用 --partial")
        retirements = load_retirements()
        states, conflicts, retired, guards = {}, {}, {}, {}
        # Validate all writes and compute all deletions before mutating any target.
        deletion_plans = {}
        for label, target_root in targets:
            for skill in skills:
                sync_entry(skill, target_root / "skills" / skill.name, True)
            sync_document(source_agents, target_root / target_document_name(label), True)
            states[label] = load_state(target_root, origin)
            if args.delete:
                deletion_plans[label], conflicts[label], retired[label], guards[label] = managed_deletions(source_skills_root, target_root / "skills", states[label], retirements, args.partial, origin / "skills")
            else:
                deletion_plans[label], conflicts[label], retired[label], guards[label] = [], [], set(), {}

        mode = "预览" if args.dry_run else "执行"
        print(f"模式：{mode}")
        print(f"Codex 源：{args.codex_root}")
        print(f"发现技能：{len(skills)}")
        print(f"同步方式：{'按管理清单清理（含退役技能）' if args.delete else '增量（保留目标独有项）'}")
        if excluded_skills:
            excluded_names = "、".join(skill.name for skill in excluded_skills)
            print(f"排除技能（MCP 或 Codex 专属）：{len(excluded_skills)}（{excluded_names}）")

        for label, target_root in targets:
            for path in deletion_plans[label]:
                print(f"{label} 待删除：{path}")
            for conflict in conflicts[label]:
                print(f"{label} 冲突：{conflict}")
            if not args.dry_run:
                for path, snapshot in guards[label].items():
                    if tree_snapshot(path) != snapshot:
                        raise SyncError(f"删除前目标已变化：{path}")
            skill_counts = Counts()
            for skill in skills:
                skill_destination = target_root / "skills" / skill.name
                existed = skill_destination.exists() or skill_destination.is_symlink()
                result = sync_entry(skill, skill_destination, args.dry_run)
                if not existed:
                    skill_counts.created += 1
                elif result.created or result.updated:
                    skill_counts.updated += 1
                else:
                    skill_counts.unchanged += 1
            document_name = target_document_name(label)
            document_status = sync_document(
                source_agents, target_root / document_name, args.dry_run
            )
            if not args.dry_run:
                # Recheck immediately before removal, after synchronization writes.
                for path, snapshot in guards[label].items():
                    if tree_snapshot(path) != snapshot:
                        raise SyncError(f"删除前目标已变化：{path}")
                apply_deletions(deletion_plans[label])
                managed = states[label]["managed"]
                for name in retired[label]:
                    managed.pop(name, None)
                for skill in skills:
                    baseline = managed.setdefault(skill.name, {})
                    # Keep pending removed-file baselines until a later --delete.
                    baseline.update(tree_snapshot(skill, source=True))
                    dest = target_root / "skills" / skill.name
                    for key in list(baseline):
                        item = dest if key == "." else dest / key
                        if not item.exists() and not item.is_symlink():
                            del baseline[key]
                write_state(target_root, states[label])
            print(
                f"{label}：{target_root} | "
                f"技能新增 {skill_counts.created}、更新 {skill_counts.updated}、"
                f"未变化 {skill_counts.unchanged} | 删除项 {len(deletion_plans[label])} | {document_name} {document_status}"
            )
        return 2 if any(conflicts.values()) else 0
    except (OSError, SyncError, ValueError, KeyError, TypeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
