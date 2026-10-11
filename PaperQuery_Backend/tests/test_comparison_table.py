import json
import unittest
from types import SimpleNamespace
from core.utils.comparison_table import parse_comparison_table
from core.skills.builtin import PaperCompareSkill, PaperCompareInput


class ComparisonTableTests(unittest.IsolatedAsyncioTestCase):
    async def test_skill_structures_fenced_output_and_preserves_original(self):
        table = {'columns': ['论文', 'methods', 'datasets', 'metrics'], 'rows': [{'论文': 'SCFormer', 'methods': 'Transformer', 'datasets': ['ETT', 'Weather'], 'metrics': ['MSE', 'MAE']}]}
        raw = '```json\n' + json.dumps(table, ensure_ascii=False) + '\n```'
        result = await PaperCompareSkill().execute(PaperCompareInput(question='比较方法'), {'llm': SimpleNamespace(invoke=lambda _: SimpleNamespace(content=raw))})
        self.assertTrue(result.ok)
        self.assertEqual(result.artifacts[0]['columns'], table['columns'])
        self.assertEqual(result.artifacts[0]['rows'], table['rows'])
        self.assertEqual(result.artifacts[0]['raw'], raw)

    def test_plain_fences_array_rows_and_malformed_output(self):
        table = {'columns': ['论文', 'metrics'], 'rows': [['A', ['MSE', 'MAE']]]}
        plain = json.dumps(table)
        expected = {'columns': ['论文', 'metrics'], 'rows': [{'论文': 'A', 'metrics': ['MSE', 'MAE']}]}
        for raw in [plain, '说明\n```JSON\n' + plain + '\n```\n结束', json.dumps(plain)]:
            self.assertEqual(parse_comparison_table(raw), expected)
        for raw in ['```json\n{"columns":["A"],', '{"columns":["A"],"rows":[null]}', '{"columns":["A","A"],"rows":[]}', '{"columns":["A"],"rows":[[1,2]]}']:
            self.assertIsNone(parse_comparison_table(raw))


if __name__ == '__main__':
    unittest.main()
