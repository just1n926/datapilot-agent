import asyncio
from pathlib import Path
import unittest

from datapilot.config import Settings
from datapilot.engine import DemoAnalysisEngine
from datapilot.evaluator import run_evaluation


class EvaluatorTests(unittest.TestCase):
    def test_bundled_cases_pass(self) -> None:
        root = Path(__file__).parents[1]
        settings = Settings(demo_file=root / "sample_data" / "sales_demo.xlsx")
        report = asyncio.run(
            run_evaluation(settings, DemoAnalysisEngine(), root / "evals" / "cases.jsonl")
        )
        self.assertEqual(report.completion_rate, 1.0)
        self.assertEqual(report.column_accuracy, 1.0)
        self.assertEqual(report.chart_accuracy, 1.0)

