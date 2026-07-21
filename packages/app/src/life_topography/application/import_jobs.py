"""In-process job supervision for one local onboarding import."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from life_topography.application.onboarding import (
    ImportPhase,
    OnboardingResult,
    OnboardingService,
)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ImportJob:
    id: str
    status: JobStatus
    phase: str
    current: int
    total: int
    result: OnboardingResult | None = None
    error: str | None = None


class ImportJobManager:
    """Runs at most one import and exposes deliberately small progress state."""

    def __init__(self, service: OnboardingService) -> None:
        self._service = service
        self._jobs: dict[str, ImportJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._lock = threading.Lock()

    def start(self, path: Path, owner_email: str) -> ImportJob:
        with self._lock:
            if any(
                job.status in {JobStatus.QUEUED, JobStatus.RUNNING} for job in self._jobs.values()
            ):
                raise RuntimeError("an import is already running")
            job = ImportJob(
                id=uuid4().hex,
                status=JobStatus.QUEUED,
                phase="queued",
                current=0,
                total=0,
            )
            self._jobs[job.id] = job
        task = asyncio.create_task(self._run(job.id, path, owner_email))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    def get(self, job_id: str) -> ImportJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active(self) -> bool:
        with self._lock:
            return any(
                job.status in {JobStatus.QUEUED, JobStatus.RUNNING} for job in self._jobs.values()
            )

    def clear(self) -> None:
        """Forget completed onboarding state after the vault is erased."""

        with self._lock:
            if any(
                job.status in {JobStatus.QUEUED, JobStatus.RUNNING} for job in self._jobs.values()
            ):
                raise RuntimeError("cannot clear jobs while an import is active")
            self._jobs.clear()

    async def _run(self, job_id: str, path: Path, owner_email: str) -> None:
        self._update(job_id, status=JobStatus.RUNNING, phase="starting")

        def progress(phase: ImportPhase, current: int, total: int) -> None:
            self._update(job_id, phase=phase.value, current=current, total=total)

        def execute() -> OnboardingResult:
            return asyncio.run(
                self._service.import_mbox(
                    path,
                    owner_email=owner_email,
                    metadata_only_consent=True,
                    progress=progress,
                )
            )

        try:
            result = await asyncio.to_thread(execute)
        except Exception:
            self._update(
                job_id,
                status=JobStatus.FAILED,
                phase="failed",
                error="Import failed. Check the file and try again.",
            )
        else:
            self._update(
                job_id,
                status=JobStatus.COMPLETED,
                phase=ImportPhase.COMPLETED.value,
                current=result.message_count,
                total=result.message_count,
                result=result,
            )

    def _update(
        self,
        job_id: str,
        *,
        status: JobStatus | str | None = None,
        phase: str | None = None,
        current: int | None = None,
        total: int | None = None,
        result: OnboardingResult | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            previous = self._jobs[job_id]
            self._jobs[job_id] = ImportJob(
                id=previous.id,
                status=JobStatus(status) if status is not None else previous.status,
                phase=phase if phase is not None else previous.phase,
                current=current if current is not None else previous.current,
                total=total if total is not None else previous.total,
                result=result if result is not None else previous.result,
                error=error if error is not None else previous.error,
            )
