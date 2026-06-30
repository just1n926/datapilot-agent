from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, load_settings
from .datasets import DatasetNotFoundError, DatasetStore, DatasetValidationError
from .engine import build_engine
from .models import AnalysisRequest, AnalysisRun, DatasetMeta
from .service import AnalysisNotFoundError, AnalysisService


def create_app(
    settings: Settings | None = None,
    store: DatasetStore | None = None,
    service: AnalysisService | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    store = store or DatasetStore(settings)
    engine = build_engine(settings)
    service = service or AnalysisService(store, engine)
    if not store.list() and settings.demo_file and settings.demo_file.is_file():
        store.load_file(settings.demo_file)

    app = FastAPI(
        title="DataPilot",
        version="0.1.0",
        description="Read-only Excel and CSV analysis agent.",
    )
    app.state.store = store
    app.state.service = service
    app.state.tasks = set()

    @app.get("/health")
    async def health() -> dict[str, str | bool | int]:
        return {
            "status": "ok",
            "engine": service.engine.name,
            "mode": settings.mode,
            "model": settings.model,
            "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
            "datasets": len(store.list()),
            "uploads_enabled": settings.allow_uploads,
        }

    @app.get("/api/datasets", response_model=list[DatasetMeta])
    async def list_datasets() -> list[DatasetMeta]:
        return store.list()

    @app.post("/api/datasets", response_model=DatasetMeta, status_code=201)
    async def upload_dataset(file: UploadFile = File(...)) -> DatasetMeta:
        if not settings.allow_uploads:
            await file.close()
            raise HTTPException(
                status_code=403,
                detail="uploads are disabled for this public demo",
            )
        try:
            data = await file.read(settings.max_upload_bytes + 1)
            return store.load_bytes(file.filename or "upload", data)
        except DatasetValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            await file.close()

    @app.get("/api/datasets/{dataset_id}", response_model=DatasetMeta)
    async def get_dataset(dataset_id: str) -> DatasetMeta:
        try:
            return store.get(dataset_id)
        except DatasetNotFoundError as exc:
            raise HTTPException(status_code=404, detail="dataset not found") from exc

    @app.get("/api/datasets/{dataset_id}/preview")
    async def preview_dataset(
        dataset_id: str,
        table: str,
        limit: int = Query(default=20, ge=1, le=50),
    ) -> dict[str, object]:
        try:
            return store.preview(dataset_id, table, limit)
        except DatasetNotFoundError as exc:
            raise HTTPException(status_code=404, detail="dataset not found") from exc
        except DatasetValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/analyses", response_model=list[AnalysisRun])
    async def list_analyses(
        limit: int = Query(default=20, ge=1, le=50),
    ) -> list[AnalysisRun]:
        return service.list(limit)

    @app.post(
        "/api/analyses",
        response_model=AnalysisRun,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_analysis(request: AnalysisRequest) -> AnalysisRun:
        try:
            run = service.start(request)
            task = asyncio.create_task(
                service.execute(run.id, request),
                name=f"datapilot-analysis-{run.id}",
            )
            app.state.tasks.add(task)
            task.add_done_callback(app.state.tasks.discard)
            return run
        except DatasetNotFoundError as exc:
            raise HTTPException(status_code=404, detail="dataset not found") from exc
        except DatasetValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/analyses/{run_id}", response_model=AnalysisRun)
    async def get_analysis(run_id: str) -> AnalysisRun:
        try:
            return service.get(run_id)
        except AnalysisNotFoundError as exc:
            raise HTTPException(status_code=404, detail="analysis not found") from exc

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
