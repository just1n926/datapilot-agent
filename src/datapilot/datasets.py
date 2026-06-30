from __future__ import annotations

import math
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from .config import Settings
from .models import DatasetColumn, DatasetMeta, DatasetTable
from .sql_safety import validate_readonly_sql


class DatasetNotFoundError(KeyError):
    pass


class DatasetValidationError(ValueError):
    pass


def normalize_identifier(value: object, fallback: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    if not text:
        text = fallback
    if text[0].isdigit():
        text = f"col_{text}"
    return text[:80]


def unique_identifiers(values: list[object], prefix: str) -> list[str]:
    result: list[str] = []
    counts: dict[str, int] = {}
    for index, value in enumerate(values, 1):
        base = normalize_identifier(value, f"{prefix}_{index}")
        counts[base] = counts.get(base, 0) + 1
        result.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
    return result


def json_value(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()  # type: ignore[union-attr]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


class DatasetStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._meta: dict[str, DatasetMeta] = {}
        self._frames: dict[str, dict[str, pd.DataFrame]] = {}

    def load_file(self, path: Path, filename: str | None = None) -> DatasetMeta:
        data = path.read_bytes()
        return self.load_bytes(filename or path.name, data)

    def load_bytes(self, filename: str, data: bytes) -> DatasetMeta:
        if not data:
            raise DatasetValidationError("uploaded file is empty")
        if len(data) > self.settings.max_upload_bytes:
            raise DatasetValidationError("uploaded file exceeds the configured size limit")
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            frames = {"data": self._read_csv(data)}
        elif suffix in {".xlsx", ".xlsm"}:
            frames = self._read_excel(data)
        else:
            raise DatasetValidationError("only .csv, .xlsx, and .xlsm files are supported")

        normalized: dict[str, pd.DataFrame] = {}
        source_names: dict[str, str] = {}
        table_names = unique_identifiers(list(frames), "table")
        for (source_name, frame), table_name in zip(frames.items(), table_names, strict=True):
            cleaned = frame.dropna(how="all").dropna(axis=1, how="all").copy()
            if cleaned.empty or not len(cleaned.columns):
                continue
            if len(cleaned) > self.settings.max_rows:
                raise DatasetValidationError(
                    f"table {source_name!r} exceeds {self.settings.max_rows} rows"
                )
            if len(cleaned.columns) > self.settings.max_columns:
                raise DatasetValidationError(
                    f"table {source_name!r} exceeds {self.settings.max_columns} columns"
                )
            original_columns = [str(column) for column in cleaned.columns]
            cleaned.columns = unique_identifiers(original_columns, "column")
            cleaned.attrs["source_columns"] = dict(
                zip(cleaned.columns, original_columns, strict=True)
            )
            normalized[table_name] = cleaned
            source_names[table_name] = source_name
        if not normalized:
            raise DatasetValidationError("the file contains no usable tabular data")

        dataset_id = uuid4().hex
        tables = [
            self._table_meta(name, source_names[name], frame)
            for name, frame in normalized.items()
        ]
        primary = max(tables, key=lambda table: table.row_count * table.column_count).name
        meta = DatasetMeta(
            id=dataset_id,
            filename=Path(filename).name,
            size_bytes=len(data),
            primary_table=primary,
            tables=tables,
        )
        self._meta[dataset_id] = meta
        self._frames[dataset_id] = normalized
        return meta

    @staticmethod
    def _read_csv(data: bytes) -> pd.DataFrame:
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return pd.read_csv(BytesIO(data), encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise DatasetValidationError(f"CSV encoding is not supported: {last_error}")

    @staticmethod
    def _read_excel(data: bytes) -> dict[str, pd.DataFrame]:
        try:
            return pd.read_excel(BytesIO(data), sheet_name=None, engine="openpyxl")
        except Exception as exc:
            raise DatasetValidationError(f"cannot read Excel workbook: {exc}") from exc

    @staticmethod
    def _table_meta(name: str, source_name: str, frame: pd.DataFrame) -> DatasetTable:
        source_columns: dict[str, str] = frame.attrs.get("source_columns", {})
        columns = []
        for column in frame.columns:
            samples = [json_value(value) for value in frame[column].dropna().head(3).tolist()]
            columns.append(
                DatasetColumn(
                    name=str(column),
                    source_name=source_columns.get(str(column), str(column)),
                    dtype=str(frame[column].dtype),
                    null_count=int(frame[column].isna().sum()),
                    samples=samples,
                )
            )
        return DatasetTable(
            name=name,
            source_name=source_name,
            row_count=len(frame),
            column_count=len(frame.columns),
            columns=columns,
        )

    def get(self, dataset_id: str) -> DatasetMeta:
        try:
            return self._meta[dataset_id]
        except KeyError as exc:
            raise DatasetNotFoundError(dataset_id) from exc

    def list(self) -> list[DatasetMeta]:
        return sorted(self._meta.values(), key=lambda item: item.created_at, reverse=True)

    def table_names(self, dataset_id: str) -> set[str]:
        self.get(dataset_id)
        return set(self._frames[dataset_id])

    def get_frame(self, dataset_id: str, table: str) -> pd.DataFrame:
        self.get(dataset_id)
        try:
            return self._frames[dataset_id][table]
        except KeyError as exc:
            raise DatasetValidationError(f"unknown table: {table}") from exc

    def preview(self, dataset_id: str, table: str, limit: int = 20) -> dict[str, object]:
        frame = self.get_frame(dataset_id, table).head(limit)
        return {
            "columns": [str(column) for column in frame.columns],
            "rows": [[json_value(value) for value in row] for row in frame.itertuples(index=False)],
        }

    def query(self, dataset_id: str, sql: str) -> tuple[list[str], list[list[object]]]:
        tables = self.table_names(dataset_id)
        query = validate_readonly_sql(sql, tables)
        connection = duckdb.connect(database=":memory:")
        try:
            connection.execute("SET enable_external_access = false")
            connection.execute("SET threads = 2")
            connection.execute("SET memory_limit = '256MB'")
            for name, frame in self._frames[dataset_id].items():
                connection.register(name, frame)
            limited = (
                f"SELECT * FROM ({query}) AS datapilot_result "
                f"LIMIT {self.settings.max_result_rows}"
            )
            cursor = connection.execute(limited)
            columns = [description[0] for description in cursor.description]
            rows = [
                [json_value(value) for value in row]
                for row in cursor.fetchall()
            ]
            return columns, rows
        finally:
            connection.close()
