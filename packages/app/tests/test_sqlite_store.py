from datetime import UTC, datetime
from pathlib import Path

import pytest
from life_topography.adapters.sqlite_store import SQLiteEvidenceStore
from life_topography.application.ingestion import IngestionKernel
from life_topography_sdk import EvidenceRecord, IngestBatch, SyncCursor, SyncMode


def incoming_batch() -> IngestBatch:
    return IngestBatch(
        connector_id="fixture",
        account_key="synthetic-account",
        mode=SyncMode.BOOTSTRAP,
        records=(
            EvidenceRecord(
                source_record_id="record-1",
                observed_at=datetime(2026, 7, 20, tzinfo=UTC),
                content_type="application/json",
                payload={"synthetic": True},
            ),
        ),
        next_cursor=SyncCursor(value="page-2"),
    )


@pytest.mark.asyncio
async def test_sqlite_store_persists_evidence_and_cursor_across_reopen(
    tmp_path: Path,
) -> None:
    database = tmp_path / "topography.db"
    first_store = SQLiteEvidenceStore(database)
    first_receipt = await IngestionKernel(first_store).ingest(incoming_batch())
    first_store.close()

    reopened = SQLiteEvidenceStore(database)
    second_receipt = await IngestionKernel(reopened).ingest(incoming_batch())

    assert first_receipt.inserted == 1
    assert second_receipt.inserted == 0
    assert second_receipt.existing == 1
    assert reopened.evidence_count == 1
    assert reopened.cursor_for("fixture", "synthetic-account") == SyncCursor(value="page-2")
    reopened.close()


def test_sqlite_store_enables_wal_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    store = SQLiteEvidenceStore(tmp_path / "topography.db")

    pragmas = store.pragmas()

    assert pragmas["journal_mode"] == "wal"
    assert pragmas["foreign_keys"] == 1
    assert pragmas["busy_timeout"] >= 5_000
    store.close()
