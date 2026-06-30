import asyncio
from pathlib import Path
import unittest

from datapilot.config import Settings
from datapilot.datasets import DatasetStore
from datapilot.engine import DemoAnalysisEngine
from datapilot.models import AnalysisRequest, AnalysisStatus
from datapilot.service import AnalysisService


class AnalysisServiceTests(unittest.TestCase):
    def test_analysis_end_to_end(self) -> None:
        store = DatasetStore(Settings())
        meta = store.load_file(Path(__file__).parents[1] / "sample_data" / "sales_demo.xlsx")
        service = AnalysisService(store, DemoAnalysisEngine())
        run = asyncio.run(
            service.create(
                AnalysisRequest(dataset_id=meta.id, question="按地区分析收入和利润")
            )
        )
        self.assertEqual(run.status, AnalysisStatus.COMPLETED)
        self.assertEqual(run.chart.type, "bar")
        self.assertTrue(run.rows)
        self.assertTrue(run.insights)

