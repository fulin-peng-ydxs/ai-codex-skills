"""Contract regressions: fixed fields, hierarchy, repetition and real template consumers."""
from pathlib import Path
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'skill-authoring-standard/scripts'))
import validate_document_template as check

CONTRACT = '''````document-template
# {{@报告名称}}

## 结论与范围
- 范围：{{@实际范围}}
- 结论：{{@证据支持的判断}}

## 问题与处理

### Q{{@序号}}：{{@名称}} <!-- repeat -->
- 证据：{{@具体来源}}
- 影响：{{@实际影响}}
- 验证：{{@结果或未执行原因}}

## 验证覆盖

| 场景 | 结果 | 证据 |
| --- | --- | --- |
| {{@场景}} | {{@真实结果}} | {{@定位}} |
````'''

GOOD = '''# 导出行为核查

## 结论与范围
- 范围：仅核查模拟导出接口及权限；用例是假设样例。
- 结论：无权限用户仍可触发导出，存在访问边界缺口。

## 问题与处理

### Q1：无权限导出
- 证据：模拟 fixture 的入口未调用授权检查。
- 影响：未获授权的用户能够导出本应不可见的数据。
- 验证：待验证：需补无权限调用用例，当前仅为格式样例。

## 验证覆盖

| 场景 | 结果 | 证据 |
| --- | --- | --- |
| 无权限调用 | 未执行；需要隔离环境 | fixture，不作为实际项目证据 |
'''


def filled(skeleton):
    """Create syntax fixtures only, never represent these as verified project reports."""
    out = skeleton
    out = re.sub(r' <!-- repeat(?:-required)? -->', '', out)
    out = check.PLACEHOLDER.sub('样例1', out)
    lines = out.splitlines()
    # Templates may declare a table with header only; add a nonempty test record.
    for index, header in reversed(check.table_headers(lines)):
        if index + 2 >= len(lines) or not lines[index + 2].strip().startswith('|'):
            lines.insert(index + 2, '| ' + ' | '.join(['无：隔离格式样例'] * len(header.split('|'))) + ' |')
    return '\n'.join(lines) + '\n'


class FixedDocumentTests(unittest.TestCase):
    def test_valid_report_and_multiple_entries(self):
        self.assertEqual([], check.validate(GOOD, CONTRACT))
        more = GOOD.replace('## 验证覆盖', '### Q2：历史数据范围\n- 证据：另一个模拟入口。\n- 影响：仅影响历史数据。\n- 验证：未验证：历史数据不可访问。\n\n## 验证覆盖')
        self.assertEqual([], check.validate(more, CONTRACT))

    def test_absence_and_unknown_are_preserved(self):
        start, end = GOOD.index('### Q1'), GOOD.index('## 验证覆盖')
        no_issues = GOOD[:start] + '条目情况：无：已检查隔离样例的正常链路。\n\n' + GOOD[end:]
        self.assertEqual([], check.validate(no_issues, CONTRACT))
        self.assertTrue(check.validate(GOOD[:start] + GOOD[end:], CONTRACT))
        unknown = GOOD.replace('模拟 fixture 的入口未调用授权检查。', '无访问权限：源码不可读；无法判断入口鉴权，需补源码后复核。')
        self.assertEqual([], check.validate(unknown, CONTRACT))
        self.assertTrue(check.validate(unknown.replace('- 证据：无访问权限：源码不可读；无法判断入口鉴权，需补源码后复核。\n', ''), CONTRACT))

    def test_fixed_structure_rejects_drift(self):
        mutations = {
            'renamed': GOOD.replace('## 结论与范围', '## 总体情况'),
            'missing-field': GOOD.replace('- 影响：未获授权的用户能够导出本应不可见的数据。\n', ''),
            'field-order': GOOD.replace('- 证据：模拟 fixture 的入口未调用授权检查。\n- 影响：未获授权的用户能够导出本应不可见的数据。', '- 影响：未获授权的用户能够导出本应不可见的数据。\n- 证据：模拟 fixture 的入口未调用授权检查。'),
            'new-field': GOOD.replace('- 影响：', '- 自由发挥：额外字段。\n- 影响：'),
            'empty-field': GOOD.replace('- 验证：待验证：需补无权限调用用例，当前仅为格式样例。', '- 验证：'),
            'changed-field-style': GOOD.replace('- 证据：模拟 fixture', '证据：模拟 fixture'),
            'new-section': GOOD + '\n## 自行新增建议\n内容。\n',
            'wrong-level': GOOD.replace('### Q1', '#### Q1'),
            'duplicate-entry': GOOD.replace('## 验证覆盖', '### Q1：另一名称\n- 证据：来源。\n- 影响：影响。\n- 验证：未验证。\n\n## 验证覆盖'),
            'wrong-columns': GOOD.replace('| 场景 | 结果 | 证据 |', '| 场景 | 结果 |'),
            'empty-cell': GOOD.replace('| 无权限调用 | 未执行；需要隔离环境 |', '| 无权限调用 | |'),
            'placeholder': GOOD.replace('未获授权的用户能够导出本应不可见的数据。', '{{@影响待填}}'),
            'leaked-marker': GOOD.replace('### Q1：无权限导出', '### Q1：无权限导出 <!-- repeat -->'),
            'headings-only': '# 标题\n## 结论与范围\n## 问题与处理\n## 验证覆盖\n',
        }
        for reason, text in mutations.items():
            with self.subTest(reason=reason):
                self.assertTrue(check.validate(text, CONTRACT))

    def test_code_headings_do_not_change_document_structure(self):
        text = GOOD.replace('## 验证覆盖', '```python\n# implementation note\n## not a document heading\n```\n\n## 验证覆盖')
        self.assertEqual([], check.validate(text, CONTRACT))

    def test_unclosed_code_fences_cannot_hide_trailing_content(self):
        broken = GOOD + '\n```python\nprint(1)\n## 意外章节\n{{@未填写}}\n'
        self.assertTrue(check.validate(broken, CONTRACT))
        broken_contract = '````document-template\n# 固定文档\n\n## 说明\n```text\n原文\n````'
        self.assertTrue(check.check_template(broken_contract))
        nested = GOOD + '\n````text\n```python\n# 原始内容\n```\n````\n'
        self.assertEqual([], check.validate(nested, CONTRACT))

    def test_design_fields_cannot_be_dropped_as_writing_instructions(self):
        source = (ROOT / 'design-spec-authoring/references/design-md-template.md').read_text()
        good = filled(check.template_blocks(source)['document'])
        self.assertEqual([], check.validate(good, source))
        for label in ['数据区', '列与长内容', '操作区', '承载容器', '桌面降级',
                      '适用任务与边界', '接入与默认呈现', '使用与禁用', '交互承接',
                      '布局与视口差异', '依据与状态']:
            with self.subTest(field=label):
                missing = re.sub(r'^- ' + re.escape(label) + r'：.*\n', '', good, flags=re.M)
                self.assertTrue(check.validate(missing, source))

    def test_handover_preparation_steps_keep_their_labels(self):
        source = (ROOT / 'project-handover-analysis/assets/project-handover-report-template.md').read_text()
        good = filled(check.template_blocks(source)['document'])
        self.assertEqual([], check.validate(good, source))
        missing = re.sub(r'^1\. .*\n', '', good, count=1, flags=re.M)
        self.assertTrue(check.validate(missing, source))

    def test_business_permission_matrix_has_a_fixed_home(self):
        source = (ROOT / 'business-closed-loop-analysis/references/output-contract.md').read_text()
        good = filled(check.template_blocks(source)['document'])
        self.assertEqual([], check.validate(good, source))
        header = '| 角色/身份 | 入口/资源 | 允许操作 | 数据范围 | 判定位置 | 业务表约束 | 缺口 |'
        missing = re.sub(re.escape(header) + r'\n\|[^\n]+\n(?:\|[^\n]+\n)*', '', good)
        self.assertTrue(check.validate(missing, source))

    def test_memory_report_retains_date_status_and_generation_time(self):
        source = (ROOT / 'backend-memory-risk-analysis/references/output-template.md').read_text()
        good = filled(check.template_blocks(source)['document'])
        self.assertEqual([], check.validate(good, source))
        for label in ['报告日期', '生成时点', '报告状态']:
            with self.subTest(field=label):
                missing = re.sub(r'^- ' + label + r'：.*\n', '', good, flags=re.M)
                self.assertTrue(check.validate(missing, source))

    def test_business_braces_are_not_template_placeholders(self):
        for value in ['`GET /records/{id}`', 'GET /records/{id}', '`{colors.primary}`',
                      '{colors.primary}', '{"status": "ok"}', '{{user.name}}', '{具体来源}']:
            with self.subTest(value=value):
                text = GOOD.replace('模拟 fixture 的入口未调用授权检查。', value)
                self.assertEqual([], check.validate(text, CONTRACT))
                self.assertEqual([], check.validate_existing(text))

    def test_explicit_unfilled_markers_still_fail(self):
        for marker in ['{{@具体来源}}', '{{@影响待填}}', '{{@尚未闭合']:
            with self.subTest(marker=marker):
                text = GOOD.replace('模拟 fixture 的入口未调用授权检查。', marker)
                self.assertTrue(check.validate(text, CONTRACT))
                self.assertTrue(check.validate_existing(text))

    def test_plain_and_bullet_fields_both_reject_unknown_names(self):
        for prefix in ['', '- ', '* ', '**']:
            with self.subTest(prefix=prefix):
                text = GOOD.replace('- 影响：', prefix + '临时自定义字段：未声明字段。\n- 影响：')
                self.assertTrue(check.validate(text, CONTRACT))
        plain_contract = CONTRACT.replace('- 证据：', '证据：').replace('- 影响：', '影响：').replace('- 验证：', '验证：')
        plain_report = GOOD.replace('- 证据：', '证据：').replace('- 影响：', '影响：').replace('- 验证：', '验证：')
        self.assertEqual([], check.validate(plain_report, plain_contract))
        self.assertTrue(check.validate(plain_report.replace('影响：', '临时自定义字段：未声明字段。\n影响：'), plain_contract))
        self.assertTrue(check.validate(GOOD.replace('- 证据：', '  - 证据：'), CONTRACT))

    def test_continuation_quotes_tables_and_free_text_keep_their_meaning(self):
        text = GOOD.replace('- 证据：模拟 fixture 的入口未调用授权检查。',
                            '- 证据：模拟 fixture 的入口未调用授权检查。\n  补充说明：这是字段内的解释。\n  - 影响：这是嵌套说明，不是另一固定字段。\n> 原始记录：静态线索。')
        text = text.replace('| 无权限调用 |', '| 场景说明：无权限调用 |')
        self.assertEqual([], check.validate(text, CONTRACT))
        free_contract = '```document-template\n# 说明\n\n## 机制\n{{@完整机制说明}}\n```'
        self.assertEqual([], check.validate('# 说明\n\n## 机制\n背景：这里是自由文本槽位。\n', free_contract))

    def test_audit_reports_require_priority_at_the_declared_position(self):
        for relative in ['frontend-ux-audit/references/output-template.md',
                         'design-compliance-audit/references/report-template.md']:
            with self.subTest(template=relative):
                source = (ROOT / relative).read_text()
                good = filled(check.template_blocks(source)['document'])
                good = re.sub(r'^优先级：.*$', '优先级：P1；依据为该技能的定级规则。', good, flags=re.M)
                self.assertEqual([], check.validate(good, source))
                missing = re.sub(r'^优先级：.*\n', '', good, flags=re.M)
                self.assertTrue(check.validate(missing, source))
                empty = re.sub(r'^优先级：.*$', '优先级：', good, flags=re.M)
                self.assertTrue(check.validate(empty, source))
                moved = re.sub(r'^优先级：.*\n', '', good, flags=re.M)
                moved = re.sub(r'^(类别：.*)$', '优先级：P1\n\\1', moved, flags=re.M)
                self.assertTrue(check.validate(moved, source))

    def test_multiple_named_entries_and_escaped_table_values(self):
        source = CONTRACT.replace('Q{{@序号}}：{{@名称}}', '对象：{{@名称}}')
        first = GOOD.replace('Q1：无权限导出', '对象：导出')
        more = first.replace('## 验证覆盖', '### 对象：历史查询\n- 证据：模拟查询入口。\n- 影响：历史记录可见范围。\n- 验证：待补隔离样例。\n\n## 验证覆盖')
        self.assertEqual([], check.validate(more, source))
        escaped = GOOD.replace('| 无权限调用 |', '| 带有 a\\|b 参数的调用 |')
        self.assertEqual([], check.validate(escaped, CONTRACT))

    def test_absence_in_declared_applicability_slot(self):
        source = CONTRACT.replace('## 问题与处理\n', '## 问题与处理\n- 适用性：{{@条件及依据}}\n')
        start, end = GOOD.index('### Q1'), GOOD.index('## 验证覆盖')
        text = GOOD[:start] + '- 适用性：不适用：隔离场景不包含问题对象。\n\n' + GOOD[end:]
        self.assertEqual([], check.validate(text, source))

    def test_required_repetition_and_template_errors(self):
        required = CONTRACT.replace('<!-- repeat -->', '<!-- repeat-required -->')
        no_items = GOOD[:GOOD.index('### Q1')] + '条目情况：无：尚无对象。\n\n' + GOOD[GOOD.index('## 验证覆盖'):]
        self.assertTrue(check.validate(no_items, required))
        self.assertTrue(check.check_template('```document-template\n# 标题'))
        self.assertTrue(check.check_template('普通示例不是完整模板'))
        self.assertTrue(check.check_template('```document-template\n# 标题\n### 错层\n正文\n```'))
        self.assertTrue(check.check_template(CONTRACT + '\n' + CONTRACT))

    def test_every_installed_template_is_consumable_and_rejects_new_sections(self):
        count = 0
        for path in sorted(ROOT.glob('*/**/*.md')):
            if any(part.startswith('.') for part in path.relative_to(ROOT).parts):
                continue
            source = path.read_text(encoding='utf-8')
            if not re.search(r'^`{3,}document-template', source, re.M):
                continue
            self.assertEqual([], check.check_template(source), str(path))
            for name, skeleton in check.template_blocks(source).items():
                with self.subTest(path=path.relative_to(ROOT), block=name):
                    text = filled(skeleton)
                    self.assertEqual([], check.validate(text, source, name), '\n'.join(check.validate(text, source, name)))
                    self.assertTrue(check.validate(text + '\n## 无授权新增章节\n额外内容\n', source, name))
                    count += 1
        self.assertGreaterEqual(count, 25)

    def test_existing_document_preserves_original_structure(self):
        existing = '# 原文\n\n## 既有安排\n保留原文细节和确认状态。\n'
        self.assertEqual([], check.validate_existing(existing))
        self.assertTrue(check.validate(existing, CONTRACT))

    def test_selected_artifacts_and_claude_thin_entry(self):
        sys.path.insert(0, str(ROOT / 'ai-constraint-doc-authoring/scripts'))
        import validate_ai_constraint_docs as ai
        source = ai.TEMPLATE.read_text()
        blocks = check.template_blocks(source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = filled(blocks['agents'])
            (root / 'AGENTS.md').write_text(agents)
            self.assertEqual([], ai.validate_repository(root, document='agents'))
            self.assertTrue(ai.validate_repository(root, document='both'))
            claude = filled(blocks['claude']).replace('样例1', 'AGENTS.md')
            (root / 'CLAUDE.md').write_text(claude)
            self.assertEqual([], ai.validate_repository(root))
            (root / 'CLAUDE.md').write_text(claude + '\n```bash\necho unsafe-copy\n```\n')
            self.assertTrue(ai.validate_repository(root, document='claude'))

    def test_cli_fixed_default_and_existing_mode_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'README.md'
            path.write_text('# 项目\n\n## 原有结构\n已有内容。\n')
            cmd = [sys.executable, str(ROOT / 'project-readme-authoring/scripts/validate_readme_structure.py'), str(path)]
            rejected = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(0, rejected.returncode)
            kept = subprocess.run(cmd + ['--existing-structure'], capture_output=True, text=True)
            self.assertEqual(0, kept.returncode, kept.stderr)
            self.assertIn('fixed-template conformance not checked', kept.stdout)

    def test_ascii_colon_fields_do_not_take_over_skill_yaml(self):
        source = (ROOT / 'skill-authoring-standard/references/skill-template.md').read_text()
        good = filled(check.template_blocks(source)['document'])
        good = good.replace('description: 样例1', 'description: 样例1\nlicense: MIT')
        self.assertEqual([], check.validate(good, source))
        ascii_contract = CONTRACT.replace('范围：', '范围:').replace('结论：', '结论:')
        report = GOOD.replace('范围：', '范围:').replace('结论：', '结论:')
        self.assertEqual([], check.validate(report, ascii_contract))
        self.assertTrue(check.validate(report.replace('- 结论:', '- 临时字段: 额外内容\n- 结论:'), ascii_contract))
        numbered = CONTRACT.replace('Q{{@序号}}：{{@名称}}', 'Q{{@序号}}: {{@名称}}')
        duplicate = GOOD.replace('Q1：无权限导出', 'Q1: Export').replace('## 验证覆盖',
            '### Q1: Another title\n- 证据：来源。\n- 影响：影响。\n- 验证：未验证。\n\n## 验证覆盖')
        self.assertTrue(check.validate(duplicate, numbered))

    def test_entrypoints_use_explicit_project_contract_without_language_modes(self):
        source = '```document-template\n# {{@项目名称}}\n\n## 项目约定\n- 用途与归属：{{@实际职责及范围}}\n- 操作入口：{{@真实入口或当前缺口}}\n```'
        good = '# 隔离样例\n\n## 项目约定\n- 用途与归属：仅检查该隔离样例的文档格式，不记录真实项目事实。\n- 操作入口：未接入实际项目；需取得真实入口后补充。\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / 'output-contract.md'
            document = root / 'document.md'
            contract.write_text(source)
            document.write_text(good)
            for skill, script in [('project-readme-authoring', 'validate_readme_structure'),
                                  ('project-module-architecture-doc-authoring', 'validate_architecture_doc_structure')]:
                with self.subTest(skill=skill):
                    entry = ROOT / skill / 'scripts' / (script + '.py')
                    cmd = [sys.executable, str(entry), str(document)]
                    self.assertNotEqual(0, subprocess.run(cmd, capture_output=True).returncode)
                    result = subprocess.run(cmd + ['--template', str(contract)], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stderr)
                    help_text = subprocess.run([sys.executable, str(entry), '--help'], capture_output=True, text=True)
                    self.assertNotIn('--language', help_text.stdout)
                    spec = importlib.util.spec_from_file_location(script, entry)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self.assertEqual([], module.validate(good, custom_structure=True))
                    with self.assertRaises(TypeError):
                        module.validate(good, '旧位置参数')
            shared = ROOT / 'skill-authoring-standard/scripts/validate_document_template.py'
            result = subprocess.run([sys.executable, str(shared), str(document), '--template', str(contract)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            document.write_text(good.replace('- 用途与归属：仅检查该隔离样例的文档格式，不记录真实项目事实。\n', ''))
            result = subprocess.run([sys.executable, str(shared), str(document), '--template', str(contract)], capture_output=True)
            self.assertNotEqual(0, result.returncode)


if __name__ == '__main__':
    unittest.main()
