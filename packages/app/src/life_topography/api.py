"""Loopback HTTP adapter for onboarding and map exploration."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from life_topography.adapters.sqlite_store import SQLiteEvidenceStore
from life_topography.application.import_jobs import ImportJob, ImportJobManager
from life_topography.application.onboarding import OnboardingService
from life_topography.connectors.demo import OWNER_EMAIL, create_demo_mbox
from life_topography.domain.topography import NodeKind


class MboxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    owner_email: str


class ImportRequest(MboxRequest):
    metadata_only_consent: bool


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: str


def create_app(database: Path, *, import_roots: Iterable[Path] | None = None) -> FastAPI:
    store = SQLiteEvidenceStore(database)
    service = OnboardingService(store)
    jobs = ImportJobManager(service)
    allowed_import_roots = _resolve_import_roots(database, import_roots)
    application = FastAPI(
        title="Life Topography",
        description="Local-first personal evidence map",
        version="0.1.0",
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "test"],
    )
    web_root = Path(__file__).parent / "web"
    application.mount("/static", StaticFiles(directory=web_root), name="static")

    @application.middleware("http")
    async def privacy_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response

    @application.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(web_root / "index.html")

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {
            "service": "life-topography",
            "status": "ok",
            "stage": "validation-mvp",
        }

    @application.post("/api/onboarding/preview")
    async def preview(request: MboxRequest) -> dict[str, object]:
        try:
            path = _confined_import_path(request.path, allowed_import_roots)
            result = service.preview_mbox(path, owner_email=request.owner_email)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Unable to read that MBOX file.") from error
        return {
            "message_count": result.message_count,
            "valid_date_count": result.valid_date_count,
            "invalid_date_count": result.invalid_date_count,
            "unique_address_count": result.unique_address_count,
            "earliest": result.earliest,
            "latest": result.latest,
            "file_size_bytes": result.file_size_bytes,
        }

    @application.post("/api/onboarding/import", status_code=status.HTTP_202_ACCEPTED)
    async def start_import(request: ImportRequest) -> dict[str, str]:
        if not request.metadata_only_consent:
            raise HTTPException(status_code=403, detail="Metadata-only consent is required.")
        try:
            path = _confined_import_path(request.path, allowed_import_roots)
            service.preview_mbox(path, owner_email=request.owner_email)
            job = jobs.start(path, request.owner_email)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Unable to read that MBOX file.") from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"job_id": job.id}

    @application.post("/api/demo", status_code=status.HTTP_202_ACCEPTED)
    async def start_demo() -> dict[str, str]:
        if store.evidence_count:
            raise HTTPException(
                status_code=409,
                detail="Erase the existing vault before loading the demo.",
            )
        try:
            path = create_demo_mbox(database.parent / "demo.mbox")
            job = jobs.start(path, OWNER_EMAIL)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"job_id": job.id}

    @application.get("/api/jobs/{job_id}")
    async def job_status(job_id: str) -> dict[str, object]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Import job not found.")
        return _job_payload(job)

    @application.get("/api/topography")
    async def topography() -> dict[str, object]:
        snapshot = service.topography()
        return {
            "summary": {
                "people": sum(node.kind is NodeKind.PERSON for node in snapshot.nodes),
                "organizations": sum(node.kind is NodeKind.ORGANIZATION for node in snapshot.nodes),
                "threads": sum(node.kind is NodeKind.THREAD for node in snapshot.nodes),
                "relationships": len(snapshot.edges),
                "evidence": store.evidence_count,
            },
            "nodes": [node.model_dump(mode="json") for node in snapshot.nodes],
            "edges": [edge.model_dump(mode="json") for edge in snapshot.edges],
        }

    @application.get("/api/evidence/{identity}")
    async def evidence(identity: str) -> dict[str, object]:
        item = service.evidence(identity)
        if item is None:
            raise HTTPException(status_code=404, detail="Evidence not found.")
        return {
            "identity": item.identity,
            "observed_at": item.record.observed_at,
            "content_type": item.record.content_type,
            "payload": item.record.payload,
        }

    @application.delete("/api/vault", status_code=status.HTTP_204_NO_CONTENT)
    async def reset(request: ResetRequest) -> Response:
        if request.confirmation != "DELETE MY MAP":
            raise HTTPException(status_code=400, detail="Confirmation phrase did not match.")
        if jobs.active():
            raise HTTPException(status_code=409, detail="Wait for the active import to finish.")
        service.reset()
        jobs.clear()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return application


def _resolve_import_roots(database: Path, roots: Iterable[Path] | None) -> tuple[Path, ...]:
    if roots is None:
        configured = os.environ.get("TOPOGRAPHY_IMPORT_ROOTS")
        roots = (
            (Path(item) for item in configured.split(os.pathsep) if item)
            if configured
            else (Path.home(), database.parent)
        )
    resolved = tuple(dict.fromkeys(path.expanduser().resolve() for path in roots))
    if not resolved:
        raise ValueError("at least one import root is required")
    return resolved


def _confined_import_path(value: str, roots: tuple[Path, ...]) -> Path:
    candidate = Path(value).expanduser().resolve()
    if not any(candidate.is_relative_to(root) for root in roots):
        raise ValueError("path is outside the configured import roots")
    return candidate


def _job_payload(job: ImportJob) -> dict[str, object]:
    return {
        "id": job.id,
        "status": job.status.value,
        "phase": job.phase,
        "current": job.current,
        "total": job.total,
        "result": (
            {
                "inserted": job.result.inserted,
                "existing": job.result.existing,
                "message_count": job.result.message_count,
                "node_count": job.result.node_count,
                "edge_count": job.result.edge_count,
            }
            if job.result is not None
            else None
        ),
        "error": job.error,
    }


_default_database = Path(
    os.environ.get(
        "TOPOGRAPHY_DATABASE",
        Path.home() / ".local" / "share" / "life-topography" / "vault.db",
    )
)
app = create_app(_default_database)
