import asyncio
from pathlib import Path
import unittest

from datapilot.config import Settings
from datapilot.datasets import DatasetStore
from datapilot.engine import DemoAnalysisEngine
from datapilot.models import AnalysisRequest


class DemoEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DatasetStore(Settings())
        demo = Path(__file__).parents[1] / "sample_data" / "sales_demo.xlsx"
        self.meta = self.store.load_file(demo)
        self.engine = DemoAnalysisEngine()

    def make_plan(self, question: str):
        return asyncio.run(
            self.engine.plan(
                self.store,
                AnalysisRequest(dataset_id=self.meta.id, question=question),
                self.meta.primary_table,
                [],
            )
        )

    def test_region_analysis(self) -> None:
        plan = self.make_plan("按地区分析收入和利润")
        self.assertEqual(plan.chart.type, "bar")
        columns, rows = self.store.query(self.meta.id, plan.sql)
        self.assertIn("margin_pct", columns)
        self.assertEqual(rows[0][0], "West")

    def test_monthly_trend(self) -> None:
        plan = self.make_plan("分析月度收入趋势")
        self.assertEqual(plan.chart.type, "line")
        self.assertEqual(plan.chart.x, "month")

    def test_anomaly_detection(self) -> None:
        plan = self.make_plan("找出收入异常订单")
        columns, rows = self.store.query(self.meta.id, plan.sql)
        self.assertIn("z_score", columns)
        self.assertTrue(rows)

