"""Connector interface owned by the public SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from life_topography_sdk.models import ConnectorManifest, IngestBatch, SyncCursor


class Connector(Protocol):
    """A source adapter supporting bootstrap and, when declared, live changes."""

    manifest: ConnectorManifest

    def bootstrap(self, cursor: SyncCursor | None = None) -> AsyncIterator[IngestBatch]:
        """Yield resumable historical batches."""
        ...

    def changes(self, cursor: SyncCursor) -> AsyncIterator[IngestBatch]:
        """Yield batches after a committed connector cursor."""
        ...
