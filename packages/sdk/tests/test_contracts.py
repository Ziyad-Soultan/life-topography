from datetime import UTC, datetime

import pytest
from life_topography_sdk.models import (
    Capability,
    ConnectorManifest,
    EvidenceRecord,
    IngestBatch,
    SyncCursor,
    SyncMode,
)
from pydantic import ValidationError


def test_manifest_rejects_incremental_mode_without_incremental_capability() -> None:
    with pytest.raises(ValidationError, match="incremental_sync"):
        ConnectorManifest(
            connector_id="fixture",
            display_name="Fixture",
            version="0.1.0",
            capabilities=frozenset({Capability.METADATA}),
            supported_modes=frozenset({SyncMode.BOOTSTRAP, SyncMode.INCREMENTAL}),
        )


def test_evidence_identity_is_stable_when_payload_changes() -> None:
    first = EvidenceRecord(
        source_record_id="message-42",
        observed_at=datetime(2026, 7, 20, tzinfo=UTC),
        content_type="application/json",
        payload={"subject": "first"},
    )
    corrected = first.model_copy(update={"payload": {"subject": "corrected"}})

    assert first.identity("gmail", "account-key") == "gmail:account-key:message-42"
    assert corrected.identity("gmail", "account-key") == first.identity("gmail", "account-key")


def test_cursor_round_trips_as_opaque_connector_state() -> None:
    cursor = SyncCursor(value="history:opaque/123==")

    restored = SyncCursor.model_validate_json(cursor.model_dump_json())

    assert restored == cursor


def test_ingest_batch_rejects_empty_record_set() -> None:
    with pytest.raises(ValidationError, match="at least one evidence record"):
        IngestBatch(
            connector_id="fixture",
            account_key="local-test",
            mode=SyncMode.BOOTSTRAP,
            records=(),
            next_cursor=SyncCursor(value="page-2"),
        )


def test_ingest_batch_rejects_duplicate_source_record_ids() -> None:
    record = EvidenceRecord(
        source_record_id="same-id",
        observed_at=datetime(2026, 7, 20, tzinfo=UTC),
        content_type="application/json",
        payload={"synthetic": True},
    )

    with pytest.raises(ValidationError, match="duplicate source_record_id"):
        IngestBatch(
            connector_id="fixture",
            account_key="local-test",
            mode=SyncMode.BOOTSTRAP,
            records=(record, record),
        )
