from __future__ import annotations

from uuid import uuid4

from .datasets import DatasetStore
from .engine import AnalysisEngine
from .models import (
    AnalysisEvent,
    AnalysisRequest,
    AnalysisRun,
    AnalysisStatus,
    ChartSpec,
    utc_now,
)


class AnalysisNotFoundError(KeyError):
    pass


class AnalysisService:
    def __init__(self, store: DatasetStore, engine: AnalysisEngine) -> None:
        self.store = store
        self.engine = engine
        self._runs: dict[str, AnalysisRun] = {}

    def start(self, request: AnalysisRequest) -> AnalysisRun:
        dataset = self.store.get(request.dataset_id)
        table = request.table or dataset.primary_table
        self.store.get_frame(request.dataset_id, table)
        run = AnalysisRun(
            id=uuid4().hex,
            status=AnalysisStatus.RUNNING,
            dataset_id=request.dataset_id,
            table=table,
            question=request.question,
            engine=self.engine.name,
            events=[AnalysisEvent(kind="system", message="Dataset and table validated")],
        )
        self._runs[run.id] = run
        return run

    async def execute(self, run_id: str, request: AnalysisRequest) -> AnalysisRun:
        run = self.get(run_id)
        try:
            plan = await self.engine.plan(
                self.store,
                request,
                run.table,
                run.events,
            )
            run.events.append(AnalysisEvent(kind="sql", message="Validating final read-only SQL"))
            columns, rows = self.store.query(run.dataset_id, plan.sql)
            chart = self._validate_chart(plan.chart, columns)
            run.title = plan.title
            run.summary = plan.summary
            run.sql = plan.sql
            run.columns = columns
            run.rows = rows
            run.chart = chart
            run.insights = self._build_insights(columns, rows, chart)
            run.status = AnalysisStatus.COMPLETED
            run.events.append(
                AnalysisEvent(kind="result", message=f"Analysis returned {len(rows)} rows")
            )
        except Exception as exc:
            run.status = AnalysisStatus.FAILED
            run.error = str(exc)
            run.events.append(AnalysisEvent(kind="error", message=str(exc)))
        run.updated_at = utc_now()
        return run

    async def create(self, request: AnalysisRequest) -> AnalysisRun:
        run = self.start(request)
        return await self.execute(run.id, request)

    def get(self, run_id: str) -> AnalysisRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise AnalysisNotFoundError(run_id) from exc

    def list(self, limit: int = 20) -> list[AnalysisRun]:
        runs = sorted(self._runs.values(), key=lambda run: run.created_at, reverse=True)
        return runs[:limit]

    @staticmethod
    def _validate_chart(chart: ChartSpec, columns: list[str]) -> ChartSpec:
        if chart.type == "none" or chart.x not in columns:
            return ChartSpec(type="none")
        y_columns = [column for column in chart.y if column in columns and column != chart.x]
        if not y_columns:
            return ChartSpec(type="none")
        return ChartSpec(type=chart.type, x=chart.x, y=y_columns[:4])

    @staticmethod
    def _build_insights(
        columns: list[str], rows: list[list[object]], chart: ChartSpec
    ) -> list[str]:
        if not rows:
            return ["The query returned no rows for the selected filters."]
        if len(rows) == 1:
            return [
                f"{column}: {value}"
                for column, value in zip(columns, rows[0], strict=True)
                if value is not None
            ][:6]
        insights: list[str] = []
        if chart.x and chart.y:
            x_index = columns.index(chart.x)
            for metric in chart.y[:2]:
                metric_index = columns.index(metric)
                numeric_rows = [row for row in rows if isinstance(row[metric_index], (int, float))]
                if numeric_rows:
                    highest = max(numeric_rows, key=lambda row: float(row[metric_index]))
                    insights.append(
                        f"{highest[x_index]} 的 {metric} 最高："
                        f"{highest[metric_index]:,.2f}。"
                    )
            if chart.type == "line" and len(rows) >= 2:
                metric_index = columns.index(chart.y[0])
                previous, latest = rows[-2][metric_index], rows[-1][metric_index]
                if (
                    isinstance(previous, (int, float))
                    and isinstance(latest, (int, float))
                    and previous
                ):
                    change = 100.0 * (latest - previous) / previous
                    insights.append(
                        f"最近一期 {chart.y[0]} 环比变化 {change:+.1f}%。"
                    )
        return insights[:4] or [f"本次分析返回 {len(rows)} 行分组结果。"]
