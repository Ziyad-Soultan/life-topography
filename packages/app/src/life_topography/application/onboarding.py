"""Consent-gated onboarding and deterministic initial map bootstrap."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from life_topography.application.ingestion import IngestionKernel
from life_topography.application.project_topography import build_topography
from life_topography.connectors.mbox import MboxConnector, MboxPreview
from life_topography.domain.topography import EvidenceItem, TopographySnapshot
from life_topography.ports.topography_store import TopographyStore


class ImportPhase(StrEnum):
    IMPORTING = "importing"
    PROJECTING = "projecting"
    COMPLETED = "completed"


ProgressCallback = Callable[[ImportPhase, int, int], None]


@dataclass(frozen=True, slots=True)
class OnboardingResult:
    inserted: int
    existing: int
    message_count: int
    node_count: int
    edge_count: int


class OnboardingService:
    """One bounded source-specific workflow over the generic ingestion kernel."""

    def __init__(self, store: TopographyStore) -> None:
        self._store = store
        self._kernel = IngestionKernel(store)

    def preview_mbox(self, path: Path, *, owner_email: str) -> MboxPreview:
        return MboxConnector(path, owner_email=owner_email).preview()

    async def import_mbox(
        self,
        path: Path,
        *,
        owner_email: str,
        metadata_only_consent: bool,
        progress: ProgressCallback | None = None,
    ) -> OnboardingResult:
        if not metadata_only_consent:
            raise PermissionError("explicit metadata-only consent is required")
        connector = MboxConnector(path, owner_email=owner_email)
        preview = connector.preview()
        cursor = self._store.cursor_for(connector.manifest.connector_id, connector.owner_email)
        inserted = 0
        existing = 0
        current = connector.cursor_position(cursor)
        _report(progress, ImportPhase.IMPORTING, current, preview.message_count)
        async for batch in connector.bootstrap(cursor):
            receipt = await self._kernel.ingest(batch)
            inserted += receipt.inserted
            existing += receipt.existing
            current = connector.cursor_position(receipt.cursor)
            _report(progress, ImportPhase.IMPORTING, current, preview.message_count)

        _report(progress, ImportPhase.PROJECTING, current, preview.message_count)
        snapshot = build_topography(
            self._store.evidence_items(), owner_addresses={connector.owner_email}
        )
        self._store.replace_topography(snapshot)
        _report(progress, ImportPhase.COMPLETED, current, preview.message_count)
        return OnboardingResult(
            inserted=inserted,
            existing=existing,
            message_count=preview.message_count,
            node_count=len(snapshot.nodes),
            edge_count=len(snapshot.edges),
        )

    def topography(self) -> TopographySnapshot:
        return self._store.load_topography()

    def evidence(self, identity: str) -> EvidenceItem | None:
        return next(
            (item for item in self._store.evidence_items() if item.identity == identity),
            None,
        )

    def reset(self) -> None:
        self._store.reset()


def _report(
    callback: ProgressCallback | None, phase: ImportPhase, current: int, total: int
) -> None:
    if callback is not None:
        callback(phase, current, total)
