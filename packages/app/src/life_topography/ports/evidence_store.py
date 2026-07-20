"""Persistence boundary required by the ingestion kernel."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from life_topography_sdk import EvidenceRecord, SyncCursor


class EvidenceTransaction(Protocol):
    """One atomic evidence-and-checkpoint transaction."""

    async def put_evidence(self, identity: str, record: EvidenceRecord) -> bool:
        """Store evidence, returning True only when newly inserted."""
        ...

    async def set_cursor(self, cursor: SyncCursor | None) -> None:
        """Stage the cursor that becomes valid with this transaction."""
        ...


class EvidenceStore(Protocol):
    """Creates source-scoped units of work."""

    def transaction(
        self, connector_id: str, account_key: str
    ) -> AbstractAsyncContextManager[EvidenceTransaction]:
        """Return an atomic transaction for one connector account."""
        ...
