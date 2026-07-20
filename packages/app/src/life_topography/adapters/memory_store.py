"""Transactional in-memory adapter for development and contract tests."""

from __future__ import annotations

from types import TracebackType

from life_topography_sdk import EvidenceRecord, SyncCursor

from life_topography.ports.evidence_store import EvidenceTransaction

SourceKey = tuple[str, str]


class InMemoryEvidenceStore:
    """Small copy-on-write store; not a production persistence adapter."""

    def __init__(self, *, fail_on_record_id: str | None = None) -> None:
        self._evidence: dict[str, EvidenceRecord] = {}
        self._cursors: dict[SourceKey, SyncCursor | None] = {}
        self._fail_on_record_id = fail_on_record_id

    @property
    def evidence_count(self) -> int:
        return len(self._evidence)

    def cursor_for(self, connector_id: str, account_key: str) -> SyncCursor | None:
        return self._cursors.get((connector_id, account_key))

    def transaction(self, connector_id: str, account_key: str) -> _InMemoryTransaction:
        return _InMemoryTransaction(self, (connector_id, account_key))


class _InMemoryTransaction(EvidenceTransaction):
    def __init__(self, store: InMemoryEvidenceStore, source_key: SourceKey) -> None:
        self._store = store
        self._source_key = source_key
        self._pending_evidence: dict[str, EvidenceRecord] = {}
        self._pending_cursor: SyncCursor | None = store.cursor_for(*source_key)

    async def __aenter__(self) -> _InMemoryTransaction:
        return self

    async def put_evidence(self, identity: str, record: EvidenceRecord) -> bool:
        if record.source_record_id == self._store._fail_on_record_id:
            raise RuntimeError("synthetic write failure")
        if identity in self._store._evidence or identity in self._pending_evidence:
            return False
        self._pending_evidence[identity] = record
        return True

    async def set_cursor(self, cursor: SyncCursor | None) -> None:
        self._pending_cursor = cursor

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self._store._evidence.update(self._pending_evidence)
            self._store._cursors[self._source_key] = self._pending_cursor
        return False
