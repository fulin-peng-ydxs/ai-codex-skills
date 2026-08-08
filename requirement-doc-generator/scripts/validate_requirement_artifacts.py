#!/usr/bin/env python3
"""Validate structural consistency across requirement artifacts.

This validator deliberately avoids judging business semantics. It catches repeatable structural
errors and leaves state, permission, data-definition, and failure-semantics review to the agent.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


CL_ID_RE = re.compile(r"\bCL-(\d+)\b")
DETAIL_HEADING_RE = re.compile(r"^###\s+(R\d+)\b\s*(.*)$", re.MULTILINE)
MANUAL_COUNT_HEADING_RE = re.compile(
    r"^#{1,6}\s+.*(?:共|含)\s*[一二三四五六七八九十百\d]+\s*项.*$", re.MULTILINE
)
ALLOWED_SUGGESTED_STATUSES = {"本次纳入", "后续建议", "已实现", "待确认", "不纳入"}
IN_SCOPE_SUGGESTED_STATUSES = {"本次纳入", "已实现"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"无法读取 {path}: {exc}") from exc


def sort_ids(values: set[str], prefix: str) -> list[str]:
    if prefix == "R":
        return sorted(values, key=lambda value: int(value[1:]))
    return sorted(values, key=lambda value: int(value.split("-", 1)[1]))


def extract_section(text: str, heading_pattern: str, next_heading_pattern: str) -> str:
    start_match = re.search(heading_pattern, text, re.MULTILINE)
    if not start_match:
        return ""
    remainder = text[start_match.end() :]
    end_match = re.search(next_heading_pattern, remainder, re.MULTILINE)
    return remainder[: end_match.start()] if end_match else remainder


def split_table_cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith(r"\|"):
        body = body[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]


def parse_r_row_list(section: str) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = split_table_cells(line)
        if cells and re.fullmatch(r"R\d+", cells[0]):
            rows.append((cells[0], cells))
    return rows


def parse_r_rows(section: str) -> dict[str, list[str]]:
    return dict(parse_r_row_list(section))


def duplicate_r_ids(rows: list[tuple[str, list[str]]]) -> set[str]:
    counts = Counter(r_id for r_id, _ in rows)
    return {r_id for r_id, count in counts.items() if count > 1}


def normalize_title(title: str) -> str:
    title = re.sub(r"[`*_~]", "", title).lower()
    return re.sub(r"[\s/\\:：·()（）\[\]【】{}<>《》\-—_]+", "", title)


def parse_scope(
    requirement: str, report: Report
) -> tuple[dict[str, set[str]], set[str], dict[str, list[str]]]:
    sections = {
        "必须实现": extract_section(
            requirement, r"^###\s+4\.1\s+必须实现\s*$", r"^(?:###\s+4\.|##\s+)"
        ),
        "建议实现": extract_section(
            requirement, r"^###\s+4\.2\s+建议实现\s*$", r"^(?:###\s+4\.|##\s+)"
        ),
        "暂不实现": extract_section(
            requirement, r"^###\s+4\.3\s+暂不实现\s*$", r"^(?:###\s+4\.|##\s+)"
        ),
    }
    categories: dict[str, set[str]] = {}
    in_scope: set[str] = set()
    scope_rows: dict[str, list[str]] = {}

    for category, section in sections.items():
        if not section:
            report.error(f"缺少范围章节：4.x {category}")
            categories[category] = set()
            continue
        row_list = parse_r_row_list(section)
        duplicates = duplicate_r_ids(row_list)
        if duplicates:
            report.error(
                f"{category}范围表内需求编号重复：{', '.join(sort_ids(duplicates, 'R'))}"
            )
        rows = dict(row_list)
        categories[category] = set(rows)
        scope_rows.update(rows)
        if category == "必须实现":
            in_scope.update(rows)
        elif category == "建议实现":
            for r_id, cells in rows.items():
                status = cells[-1] if cells else ""
                if status not in ALLOWED_SUGGESTED_STATUSES:
                    report.error(
                        f"{r_id} 建议实现项最后一列必须是合法处理状态，"
                        "实际为："
                        f"{status or '无'}"
                    )
                    continue
                if status in IN_SCOPE_SUGGESTED_STATUSES:
                    in_scope.add(r_id)

    category_names = list(categories)
    for index, left_name in enumerate(category_names):
        for right_name in category_names[index + 1 :]:
            overlap = categories[left_name] & categories[right_name]
            if overlap:
                report.error(
                    f"范围分类冲突：{left_name} 与 {right_name} 重复包含 "
                    f"{', '.join(sort_ids(overlap, 'R'))}"
                )
    return categories, in_scope, scope_rows


def validate_requirement(requirement: str, report: Report) -> None:
    categories, in_scope, scope_rows = parse_scope(requirement, report)
    declared = set().union(*categories.values())

    detail_matches = DETAIL_HEADING_RE.findall(requirement)
    detailed = {r_id for r_id, _ in detail_matches}
    detail_titles = {r_id: title.strip() for r_id, title in detail_matches}
    duplicate_details = {r_id for r_id in detailed if sum(m[0] == r_id for m in detail_matches) > 1}
    if duplicate_details:
        report.error(f"详细需求标题重复：{', '.join(sort_ids(duplicate_details, 'R'))}")

    for r_id, cells in scope_rows.items():
        if r_id not in detail_titles or len(cells) < 2:
            continue
        scope_title = normalize_title(cells[1])
        detail_title = normalize_title(detail_titles[r_id])
        titles_differ = (
            scope_title
            and detail_title
            and scope_title not in detail_title
            and detail_title not in scope_title
        )
        if titles_differ:
            report.warn(
                f"{r_id} 范围标题“{cells[1]}”与详细需求标题"
                f"“{detail_titles[r_id]}”"
                "差异较大，请确认编号语义未变化"
            )

    acceptance_section = extract_section(
        requirement, r"^##\s+11\.\s*验收标准\s*$", r"^##\s+"
    )
    if not acceptance_section:
        report.error("缺少“11. 验收标准”章节")
        accepted: set[str] = set()
    else:
        acceptance_rows = parse_r_row_list(acceptance_section)
        duplicate_acceptance = duplicate_r_ids(acceptance_rows)
        if duplicate_acceptance:
            report.error(
                "验收标准表内需求编号重复："
                f"{', '.join(sort_ids(duplicate_acceptance, 'R'))}"
            )
        accepted = {r_id for r_id, _ in acceptance_rows}

    missing_details = in_scope - detailed
    if missing_details:
        missing = ", ".join(sort_ids(missing_details, "R"))
        report.error(f"本期需求缺少详细需求：{missing}")

    missing_acceptance = in_scope - accepted
    if missing_acceptance:
        missing = ", ".join(sort_ids(missing_acceptance, "R"))
        report.error(f"本期需求缺少验收标准：{missing}")

    unknown_acceptance = accepted - declared
    if unknown_acceptance:
        unknown = ", ".join(sort_ids(unknown_acceptance, "R"))
        report.error(f"验收标准引用未声明需求：{unknown}")

    unknown_details = detailed - declared
    if unknown_details:
        unknown = ", ".join(sort_ids(unknown_details, "R"))
        report.error(f"详细需求引用未声明需求：{unknown}")

    if re.search(r"(?:阻塞确认项\s*[：:]\s*无|无剩余阻塞项)", requirement):
        suggested_section = extract_section(
            requirement, r"^###\s+4\.2\s+建议实现\s*$", r"^(?:###\s+4\.|##\s+)"
        )
        if any("待确认" in cells for cells in parse_r_rows(suggested_section).values()):
            report.error(
                "文档声明无剩余阻塞项，"
                "但建议实现范围仍存在“待确认”条目"
            )


def validate_handoff(
    requirement: str, closure: str, report: Report, allow_legacy_closure: bool
) -> None:
    closure_rows: list[str] = []
    for line in closure.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = split_table_cells(line)
        if cells and re.fullmatch(r"CL-\d+", cells[0]):
            closure_rows.append(cells[0])

    closure_ids = set(closure_rows)
    requirement_ids = {f"CL-{value}" for value in CL_ID_RE.findall(requirement)}

    if not closure_ids:
        if allow_legacy_closure:
            report.warn(
                "历史闭环文档缺少 CL-xx 交接键，本次按语义继承；"
                "后续更新时需迁移"
            )
            return
        report.error("闭环文档的交接清单缺少稳定 CL-xx 交接键")
        return

    duplicate_rows = {cl_id for cl_id in closure_ids if closure_rows.count(cl_id) > 1}
    if duplicate_rows:
        report.error(f"闭环交接键重复：{', '.join(sort_ids(duplicate_rows, 'CL'))}")

    missing = closure_ids - requirement_ids
    if missing:
        report.error(f"需求文档未映射闭环交接键：{', '.join(sort_ids(missing, 'CL'))}")

    unknown = requirement_ids - closure_ids
    if unknown:
        unknown_ids = ", ".join(sort_ids(unknown, "CL"))
        report.error(f"需求文档引用不存在的闭环交接键：{unknown_ids}")


def validate_markdown(path: Path, text: str, report: Report) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.rstrip() != line:
            report.warn(f"{path}:{line_number} 存在行尾空白")

    for match in MANUAL_COUNT_HEADING_RE.finditer(text):
        line_number = text.count("\n", 0, match.start()) + 1
        report.warn(
            f"{path}:{line_number} 标题手工声明条目数量，建议改由清单表达"
        )

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        start = index
        group: list[str] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            group.append(lines[index])
            index += 1
        if len(group) < 2 or not re.fullmatch(r"[|:\-\s]+", group[1]):
            continue
        expected = len(split_table_cells(group[0]))
        for offset, line in enumerate(group[1:], start=1):
            actual = len(split_table_cells(line))
            if actual != expected:
                report.error(
                    f"{path}:{start + offset + 1} Markdown 表格列数不一致："
                    f"期望 {expected}，实际 {actual}"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="校验需求闭环与需求文档的结构一致性"
    )
    parser.add_argument("--requirement", type=Path, required=True, help="requirement.md 路径")
    parser.add_argument("--closure", type=Path, help="requirement-closure.md 路径")
    parser.add_argument(
        "--research",
        type=Path,
        help="可选 research.md 路径，仅做 Markdown 结构检查",
    )
    parser.add_argument(
        "--allow-legacy-closure",
        action="store_true",
        help="允许无 CL-xx 的历史闭环文档通过，并输出迁移警告",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = Report()
    requirement = read_text(args.requirement)

    validate_requirement(requirement, report)
    validate_markdown(args.requirement, requirement, report)

    if args.closure:
        closure = read_text(args.closure)
        validate_handoff(requirement, closure, report, args.allow_legacy_closure)
        validate_markdown(args.closure, closure, report)
    if args.research:
        research = read_text(args.research)
        validate_markdown(args.research, research, report)

    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")

    if report.errors:
        print(f"校验失败：{len(report.errors)} 个错误，{len(report.warnings)} 个警告")
        return 1
    print(f"校验通过：0 个错误，{len(report.warnings)} 个警告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
