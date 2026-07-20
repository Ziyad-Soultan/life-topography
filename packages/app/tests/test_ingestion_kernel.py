from datetime import UTC, datetime

import pytest
from life_topography.adapters.memory_store import InMemoryEvidenceStore
from life_topography.application.ingestion import IngestionKernel
from life_topography_sdk import EvidenceRecord, IngestBatch, SyncCursor, SyncMode


def record(record_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        source_record_id=record_id,
        observed_at=datetime(2026, 7, 20, tzinfo=UTC),
        content_type="application/json",
        payload={"synthetic": True, "record_id": record_id},
    )


def batch(*records: EvidenceRecord, cursor: str = "next-page") -> IngestBatch:
    return IngestBatch(
        connector_id="fixture",
        account_key="synthetic-account",
        mode=SyncMode.BOOTSTRAP,
        records=records,
        next_cursor=SyncCursor(value=cursor),
    )


@pytest.mark.asyncio
async def test_duplicate_batch_is_idempotent() -> None:
    store = InMemoryEvidenceStore()
    kernel = IngestionKernel(store)
    incoming = batch(record("one"))

    first = await kernel.ingest(incoming)
    second = await kernel.ingest(incoming)

    assert first.inserted == 1
    assert first.existing == 0
    assert second.inserted == 0
    assert second.existing == 1
    assert store.evidence_count == 1
    assert store.cursor_for("fixture", "synthetic-account") == SyncCursor(value="next-page")


@pytest.mark.asyncio
async def test_failed_evidence_write_rolls_back_records_and_cursor() -> None:
    store = InMemoryEvidenceStore(fail_on_record_id="explode")
    kernel = IngestionKernel(store)

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        await kernel.ingest(batch(record("written-first"), record("explode")))

    assert store.evidence_count == 0
    assert store.cursor_for("fixture", "synthetic-account") is None


@pytest.mark.asyncio
async def test_cursor_advances_only_after_every_record_is_durable() -> None:
    store = InMemoryEvidenceStore()
    kernel = IngestionKernel(store)

    receipt = await kernel.ingest(batch(record("one"), record("two"), cursor="history-42"))

    assert receipt.inserted == 2
    assert receipt.existing == 0
    assert receipt.cursor == SyncCursor(value="history-42")
    assert store.cursor_for("fixture", "synthetic-account") == receipt.cursor
