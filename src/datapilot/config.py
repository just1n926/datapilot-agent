from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class Settings:
    model: str = "gpt-5.4-mini"
    mode: Literal["auto", "openai", "demo"] = "auto"
    max_upload_bytes: int = 20 * 1024 * 1024
    max_rows: int = 200_000
    max_columns: int = 200
    max_result_rows: int = 500
    max_agent_turns: int = 10
    demo_file: Path | None = None
    allow_uploads: bool = True


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    mode = os.getenv("DATAPILOT_MODE", "auto").lower()
    if mode not in {"auto", "openai", "demo"}:
        raise ValueError("DATAPILOT_MODE must be auto, openai, or demo")
    demo_default = Path(__file__).parents[2] / "sample_data" / "sales_demo.xlsx"
    demo_value = os.getenv("DATAPILOT_DEMO_FILE")
    return Settings(
        model=os.getenv("DATAPILOT_MODEL", "gpt-5.4-mini"),
        mode=mode,  # type: ignore[arg-type]
        max_upload_bytes=int(os.getenv("DATAPILOT_MAX_UPLOAD_MB", "20")) * 1024 * 1024,
        max_rows=int(os.getenv("DATAPILOT_MAX_ROWS", "200000")),
        max_columns=int(os.getenv("DATAPILOT_MAX_COLUMNS", "200")),
        max_result_rows=int(os.getenv("DATAPILOT_MAX_RESULT_ROWS", "500")),
        max_agent_turns=int(os.getenv("DATAPILOT_MAX_AGENT_TURNS", "10")),
        demo_file=Path(demo_value).resolve() if demo_value else demo_default,
        allow_uploads=_env_bool("DATAPILOT_ALLOW_UPLOADS", True),
    )
