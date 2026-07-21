"""Persistence boundary for evidence and its replaceable topography."""

from __future__ import annotations

from typing import Protocol

from life_topography_sdk import SyncCursor

from life_topography.domain.topography import EvidenceItem, TopographySnapshot
from life_topography.ports.evidence_store import EvidenceStore


class TopographyStore(EvidenceStore, Protocol):
    @property
    def evidence_count(self) -> int: ...

    def cursor_for(self, connector_id: str, account_key: str) -> SyncCursor | None: ...

    def evidence_items(self) -> list[EvidenceItem]: ...

    def replace_topography(self, snapshot: TopographySnapshot) -> None: ...

    def load_topography(self) -> TopographySnapshot: ...

    def reset(self) -> None: ...
