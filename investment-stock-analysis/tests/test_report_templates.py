"""Exercise report-mode and publication templates through the shared checker.

All documents and financial inputs here are synthetic; no real archive is read
or written. Structural checks do not claim to validate investment conclusions.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
CHECKER = SKILL.parent / 'skill-authoring-standard/scripts/validate_document_template.py'
REPORTS = SKILL / 'references/report-templates.md'
TRACKING = SKILL / 'references/tracking.md'


def fixture(template, block):
    """Fill the authoritative structure, leaving validation to the shared tool."""
    content = re.search(r'````document-template ' + block + r'\n(.*?)\n````',
                        template.read_text(), re.S).group(1)
    return re.sub(r'\{\{@.*?\}\}', '合成夹具：受阻，尚无可用原始输入', content)


class ReportModeTemplates(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.gettempdir()) / 'ai-agent/ai-codex-skills'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='stock-template-', dir=base)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, content, template, block, valid=True):
        path = self.root / (block + '-report.md')
        path.write_text(content)
        result = subprocess.run([sys.executable, '-B', str(CHECKER), str(path),
                                 '--template', str(template), '--block', block],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, valid, result.stdout + result.stderr)
        return path

    def test_full_preserves_required_structure_with_missing_inputs(self):
        self.validate(fixture(REPORTS, 'full'), REPORTS, 'full')

    def test_full_cannot_drop_forecast_or_price_tier_rows(self):
        document = fixture(REPORTS, 'full')
        for prefix in ['| FY2 |', '| 第三档 |']:
            with self.subTest(row=prefix):
                damaged = '\n'.join(line for line in document.splitlines()
                                    if not line.startswith(prefix))
                self.validate(damaged, REPORTS, 'full', False)

    def test_full_cannot_drop_peer_comparison(self):
        document = fixture(REPORTS, 'full')
        damaged = re.sub(r'^\| 公司 \|.*?(?=\n\n)', '', document, flags=re.M | re.S)
        self.assertNotEqual(document, damaged)
        self.validate(damaged, REPORTS, 'full', False)

    def test_scoped_can_represent_completion_partial_or_blocked(self):
        document = fixture(REPORTS, 'scoped')
        for state in ['专项完成', '部分完成', '受阻']:
            with self.subTest(state=state):
                scoped = re.sub(r'^- 报告状态：.*$', '- 报告状态：' + state,
                                document, flags=re.M)
                self.validate(scoped, REPORTS, 'scoped')

    def test_scoped_score_rows_can_include_all_fifteen_items(self):
        document = fixture(REPORTS, 'scoped')
        row = next(line for line in document.splitlines() if line.startswith('| 合成夹具'))
        rows = '\n'.join(f'| {i} 合成评分项 | 原定窗口 | 未评分 | 缺合格来源G01 |'
                         for i in range(1, 16))
        self.validate(document.replace(row, rows), REPORTS, 'scoped')

    def test_scoped_requires_scope_and_evidence_sections(self):
        document = fixture(REPORTS, 'scoped')
        for damaged in [re.sub(r'^- 研究范围：.*\n', '', document, flags=re.M),
                        re.sub(r'## 来源与计算核验\n.*?(?=## 保存与后续)',
                               '', document, flags=re.S)]:
            self.validate(damaged, REPORTS, 'scoped', False)

    def test_publication_state_has_two_core_rows(self):
        self.validate(fixture(TRACKING, 'state'), TRACKING, 'state')

    def test_publication_state_rejects_missing_record_hash_row(self):
        document = fixture(TRACKING, 'state')
        document = '\n'.join(line for line in document.splitlines()
                             if not line.startswith('| 研究记录 |'))
        self.validate(document, TRACKING, 'state', False)

    def test_publication_state_rejects_duplicated_business_ledger(self):
        document = fixture(TRACKING, 'state') + '\n\n## 数据缺口\n\n重复业务台账G01\n'
        self.validate(document, TRACKING, 'state', False)

    def test_saved_scoped_report_publishes_one_consolidated_record(self):
        """Use the actual CLI for a new saved dividend-yield fixture."""
        document = fixture(REPORTS, 'scoped')
        document = document.replace('合成夹具：受阻，尚无可用原始输入',
                                    '合成夹具：仅股息率，输入已核验，5%，无缺口')
        document = re.sub(r'^- 研究截止：.*$', '- 研究截止：2026-11-01T10:00:00+08:00',
                          document, flags=re.M)
        document = re.sub(r'^- 报告状态：.*$', '- 报告状态：专项完成', document, flags=re.M)
        report = self.validate(document, REPORTS, 'scoped')
        records = self.root / 'research.json'
        records.write_text(json.dumps({
            'plan': {'subject': 'TEST.SH', 'mode': 'scoped'},
            'sources': [{'id': 'S1', 'fixture': True}],
            'data': [{'id': 'dps', 'value': 1, 'status': 'verified'},
                     {'id': 'price', 'value': 20, 'status': 'verified'}],
            'calculations': [{'id': 'yield', 'formula': 'dps/price*100',
                              'input_ids': ['dps', 'price'], 'output': 5}],
            'analyses': [{'id': 'dividend-yield', 'status': 'passed',
                          'raw_required_input_ids': ['dps', 'price'],
                          'output_ids': ['yield']}],
            'gaps': [],
            'verification': [{'status': 'passed', 'check': '1/20*100=5'}],
        }))
        state = fixture(TRACKING, 'state')
        state = re.sub(r'^- 研究截止：.*$', '- 研究截止：2026-11-01T10:00:00+08:00',
                       state, flags=re.M)
        state = re.sub(r'^- 当前报告：.*$', '- 当前报告：[report.md](report.md)', state, flags=re.M)
        state = re.sub(r'^\| 报告 \|.*$', '| 报告 | [report.md](report.md) | '
                       + hashlib.sha256(report.read_bytes()).hexdigest() + ' |', state, flags=re.M)
        state = re.sub(r'^\| 研究记录 \|.*$',
                       '| 研究记录 | [research.json](evidence/research.json) | '
                       + hashlib.sha256(records.read_bytes()).hexdigest() + ' |', state, flags=re.M)
        candidate = self.validate(state, TRACKING, 'state')
        company = self.root / 'company'
        company.mkdir()
        mapping = self.root / 'artifacts.json'
        mapping.write_text(json.dumps({'report.md': str(report),
                                       'evidence/research.json': str(records)}))
        result = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts/publish_state.py'),
                                 '--directory', str(company), '--candidate', str(candidate),
                                 '--artifacts', str(mapping), '--expected', 'absent'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((company / 'report.md').read_bytes(), report.read_bytes())
        self.assertEqual((company / 'state.md').read_bytes(), candidate.read_bytes())
        actual = json.loads((company / 'evidence/research.json').read_text())
        self.assertEqual(actual['calculations'][0]['output'],
                         actual['data'][0]['value'] / actual['data'][1]['value'] * 100)
        self.assertEqual({p.relative_to(company).as_posix() for p in company.rglob('*')
                          if p.is_file()},
                         {'.state.lock', 'state.md', 'report.md', 'evidence/research.json'})


if __name__ == '__main__':
    unittest.main()
