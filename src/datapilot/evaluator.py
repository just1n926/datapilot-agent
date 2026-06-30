from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .config import Settings
from .datasets import DatasetStore
from .engine import AnalysisEngine
from .models import AnalysisRequest, AnalysisStatus
from .service import AnalysisService


class EvalCase(BaseModel):
    id: str
    question: str
    expected_columns: list[str]
    expected_chart: str


class EvalCaseResult(BaseModel):
    id: str
    completed: bool
    columns_correct: bool
    chart_correct: bool
    error: str | None = None


class EvalReport(BaseModel):
    total: int
    completion_rate: float
    column_accuracy: float
    chart_accuracy: float
    cases: list[EvalCaseResult]


def load_cases(path: str | Path) -> list[EvalCase]:
    cases = [
        EvalCase.model_validate_json(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not cases:
        raise ValueError("evaluation dataset is empty")
    return cases


async def run_evaluation(
    settings: Settings,
    engine: AnalysisEngine,
    cases_path: str | Path,
) -> EvalReport:
    if not settings.demo_file or not settings.demo_file.is_file():
        raise FileNotFoundError("demo workbook is required for evaluation")
    store = DatasetStore(settings)
    dataset = store.load_file(settings.demo_file)
    service = AnalysisService(store, engine)
    results: list[EvalCaseResult] = []
    for case in load_cases(cases_path):
        run = await service.create(
            AnalysisRequest(dataset_id=dataset.id, question=case.question)
        )
        results.append(
            EvalCaseResult(
                id=case.id,
                completed=run.status == AnalysisStatus.COMPLETED,
                columns_correct=set(case.expected_columns).issubset(run.columns),
                chart_correct=run.chart.type == case.expected_chart,
                error=run.error,
            )
        )
    total = len(results)
    return EvalReport(
        total=total,
        completion_rate=sum(result.completed for result in results) / total,
        column_accuracy=sum(result.columns_correct for result in results) / total,
        chart_accuracy=sum(result.chart_correct for result in results) / total,
        cases=results,
    )


def report_json(report: EvalReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)

