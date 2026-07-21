from datetime import UTC, datetime
from pathlib import Path
from stat import S_IMODE

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


@pytest.mark.asyncio
async def test_reset_removes_deleted_content_from_database_and_sidecars(tmp_path: Path) -> None:
    database = tmp_path / "topography.db"
    marker = "PRIVATE-DELETION-MARKER-7c97e89a"
    store = SQLiteEvidenceStore(database)
    batch = IngestBatch(
        connector_id="fixture",
        account_key="synthetic-account",
        mode=SyncMode.BOOTSTRAP,
        records=(
            EvidenceRecord(
                source_record_id=marker,
                observed_at=datetime(2026, 7, 20, tzinfo=UTC),
                content_type="application/json",
                payload={"private_marker": marker},
            ),
        ),
        next_cursor=SyncCursor(value="page-2"),
    )
    await IngestionKernel(store).ingest(batch)

    store.reset()

    assert store.evidence_count == 0
    encoded_marker = marker.encode()
    for path in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
        if path.exists():
            assert encoded_marker not in path.read_bytes()
    store.close()


def test_sqlite_store_enables_wal_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    database = tmp_path / "topography.db"
    store = SQLiteEvidenceStore(database)

    pragmas = store.pragmas()

    assert pragmas["journal_mode"] == "wal"
    assert pragmas["foreign_keys"] == 1
    assert pragmas["busy_timeout"] >= 5_000
    assert pragmas["secure_delete"] == 1
    assert S_IMODE(database.stat().st_mode) == 0o600
    store.close()
