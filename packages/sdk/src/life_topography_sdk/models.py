"""Stable, framework-independent ingestion contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class Capability(StrEnum):
    """Data and lifecycle capabilities declared by a connector."""

    METADATA = "metadata"
    CONTENT = "content"
    ATTACHMENTS = "attachments"
    INCREMENTAL_SYNC = "incremental_sync"
    RECONCILIATION = "reconciliation"
    DELETION = "deletion"


class SyncMode(StrEnum):
    """The lifecycle phase producing an ingestion batch."""

    BOOTSTRAP = "bootstrap"
    INCREMENTAL = "incremental"
    RECONCILE = "reconcile"


class ConnectorManifest(BaseModel):
    """A connector's explicit capabilities and supported lifecycle modes."""

    model_config = ConfigDict(frozen=True)

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    display_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    capabilities: frozenset[Capability]
    supported_modes: frozenset[SyncMode]

    @model_validator(mode="after")
    def capabilities_cover_modes(self) -> ConnectorManifest:
        if (
            SyncMode.INCREMENTAL in self.supported_modes
            and Capability.INCREMENTAL_SYNC not in self.capabilities
        ):
            raise ValueError("incremental_sync capability is required for incremental mode")
        if (
            SyncMode.RECONCILE in self.supported_modes
            and Capability.RECONCILIATION not in self.capabilities
        ):
            raise ValueError("reconciliation capability is required for reconcile mode")
        return self


class SyncCursor(BaseModel):
    """Opaque state owned and interpreted by one connector."""

    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1)


class EvidenceRecord(BaseModel):
    """Immutable source-shaped evidence before canonical interpretation."""

    model_config = ConfigDict(frozen=True)

    source_record_id: str = Field(min_length=1)
    observed_at: datetime
    content_type: str = Field(min_length=1)
    payload: dict[str, JsonValue]

    def identity(self, connector_id: str, account_key: str) -> str:
        """Return the stable, source-scoped idempotency identity."""

        return f"{connector_id}:{account_key}:{self.source_record_id}"


class IngestBatch(BaseModel):
    """An atomic group of evidence and the cursor unlocked by committing it."""

    model_config = ConfigDict(frozen=True)

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    account_key: str = Field(min_length=1)
    mode: SyncMode
    records: tuple[EvidenceRecord, ...]
    next_cursor: SyncCursor | None = None

    @model_validator(mode="after")
    def records_are_nonempty_and_unique(self) -> IngestBatch:
        if not self.records:
            raise ValueError("batch must contain at least one evidence record")
        record_ids = [record.source_record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("batch contains duplicate source_record_id values")
        return self
