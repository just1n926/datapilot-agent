from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class DatasetColumn(BaseModel):
    name: str
    source_name: str
    dtype: str
    null_count: int
    samples: list[object] = Field(default_factory=list)


class DatasetTable(BaseModel):
    name: str
    source_name: str
    row_count: int
    column_count: int
    columns: list[DatasetColumn]


class DatasetMeta(BaseModel):
    id: str
    filename: str
    size_bytes: int
    created_at: datetime = Field(default_factory=utc_now)
    primary_table: str
    tables: list[DatasetTable]


class ChartSpec(BaseModel):
    type: Literal["none", "bar", "line"] = "none"
    x: str | None = None
    y: list[str] = Field(default_factory=list, max_length=4)


class AnalysisPlan(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2_000)
    sql: str = Field(min_length=1, max_length=8_000)
    chart: ChartSpec = Field(default_factory=ChartSpec)


class AnalysisStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisEvent(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    kind: str
    message: str


class AnalysisRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=4, max_length=5_000)
    table: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())


class AnalysisRun(BaseModel):
    id: str
    status: AnalysisStatus
    dataset_id: str
    table: str
    question: str
    engine: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    title: str | None = None
    summary: str | None = None
    sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[object]] = Field(default_factory=list)
    chart: ChartSpec = Field(default_factory=ChartSpec)
    insights: list[str] = Field(default_factory=list)
    events: list[AnalysisEvent] = Field(default_factory=list)
    error: str | None = None

