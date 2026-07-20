"""Transactional ingestion orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from life_topography_sdk import IngestBatch, SyncCursor

from life_topography.ports.evidence_store import EvidenceStore


@dataclass(frozen=True, slots=True)
class IngestReceipt:
    """Observable result of a committed ingestion batch."""

    inserted: int
    existing: int
    cursor: SyncCursor | None


class IngestionKernel:
    """Commits evidence idempotently before advancing its source cursor."""

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    async def ingest(self, batch: IngestBatch) -> IngestReceipt:
        inserted = 0
        existing = 0
        async with self._store.transaction(batch.connector_id, batch.account_key) as transaction:
            for record in batch.records:
                identity = record.identity(batch.connector_id, batch.account_key)
                if await transaction.put_evidence(identity, record):
                    inserted += 1
                else:
                    existing += 1
            await transaction.set_cursor(batch.next_cursor)

        return IngestReceipt(inserted=inserted, existing=existing, cursor=batch.next_cursor)
