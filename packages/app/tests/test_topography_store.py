from datetime import UTC, datetime
from pathlib import Path

import pytest
from life_topography.adapters.sqlite_store import SQLiteEvidenceStore
from life_topography.application.ingestion import IngestionKernel
from life_topography.application.project_topography import build_topography
from life_topography_sdk import EvidenceRecord, IngestBatch, SyncCursor, SyncMode


def email_record() -> EvidenceRecord:
    return EvidenceRecord(
        source_record_id="message-id:one@example.test",
        observed_at=datetime(2026, 6, 1, tzinfo=UTC),
        content_type="application/vnd.life-topography.email-headers+json",
        payload={
            "kind": "email_headers",
            "message_id": "one@example.test",
            "sent_at": "2026-06-01T00:00:00+00:00",
            "date_valid": True,
            "subject": "Private map",
            "normalized_subject": "private map",
            "sender": {"address": "ada@analytical.engine", "name": "Ada"},
            "recipients": [{"address": "owner@example.net", "name": "Owner"}],
        },
    )


@pytest.mark.asyncio
async def test_projection_persists_with_provenance_across_reopen(tmp_path: Path) -> None:
    database = tmp_path / "topography.db"
    store = SQLiteEvidenceStore(database)
    await IngestionKernel(store).ingest(
        IngestBatch(
            connector_id="mbox",
            account_key="owner@example.net",
            mode=SyncMode.BOOTSTRAP,
            records=(email_record(),),
            next_cursor=SyncCursor(value="1"),
        )
    )
    expected = build_topography(store.evidence_items(), owner_addresses={"owner@example.net"})
    store.replace_topography(expected)
    store.close()

    reopened = SQLiteEvidenceStore(database)

    assert reopened.load_topography() == expected
    assert all(node.evidence_ids for node in reopened.load_topography().nodes)
    reopened.close()


@pytest.mark.asyncio
async def test_reset_removes_source_and_every_projection(tmp_path: Path) -> None:
    store = SQLiteEvidenceStore(tmp_path / "topography.db")
    await IngestionKernel(store).ingest(
        IngestBatch(
            connector_id="mbox",
            account_key="owner@example.net",
            mode=SyncMode.BOOTSTRAP,
            records=(email_record(),),
            next_cursor=SyncCursor(value="1"),
        )
    )
    store.replace_topography(
        build_topography(store.evidence_items(), owner_addresses={"owner@example.net"})
    )

    store.reset()

    assert store.evidence_count == 0
    assert store.cursor_for("mbox", "owner@example.net") is None
    assert store.evidence_items() == []
    assert store.load_topography().nodes == ()
    assert store.load_topography().edges == ()
    store.close()
