import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from datapilot.config import Settings
from datapilot.datasets import DatasetStore
from datapilot.engine import OpenAIAnalysisEngine
from datapilot.models import AnalysisPlan, AnalysisRequest, ChartSpec


class OpenAIEngineTests(unittest.TestCase):
    def test_tools_register_with_installed_sdk(self) -> None:
        store = DatasetStore(Settings())
        meta = store.load_file(Path(__file__).parents[1] / "sample_data" / "sales_demo.xlsx")
        plan = AnalysisPlan(
            title="Overview",
            summary="Mocked result",
            sql="SELECT COUNT(*) orders FROM sales_data",
            chart=ChartSpec(type="none"),
        )
        runner = AsyncMock(return_value=SimpleNamespace(final_output=plan))
        engine = OpenAIAnalysisEngine(Settings(mode="openai", model="test-model"))
        with patch("agents.Runner.run", new=runner):
            result = asyncio.run(
                engine.plan(
                    store,
                    AnalysisRequest(dataset_id=meta.id, question="总结核心指标"),
                    meta.primary_table,
                    [],
                )
            )
        self.assertEqual(result, plan)
        self.assertEqual(len(runner.await_args.args[0].tools), 3)
        self.assertFalse(runner.await_args.kwargs["run_config"].trace_include_sensitive_data)

