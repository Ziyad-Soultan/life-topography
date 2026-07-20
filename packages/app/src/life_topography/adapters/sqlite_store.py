"""SQLite evidence adapter with atomic evidence/cursor commits."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

from life_topography_sdk import EvidenceRecord, SyncCursor
from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection
from sqlalchemy.engine.base import RootTransaction

from life_topography.ports.evidence_store import EvidenceTransaction

metadata = MetaData()

evidence = Table(
    "evidence",
    metadata,
    Column("identity", String, primary_key=True),
    Column("connector_id", String, nullable=False),
    Column("account_key", String, nullable=False),
    Column("source_record_id", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("content_type", String, nullable=False),
    Column("record_json", Text, nullable=False),
    UniqueConstraint("connector_id", "account_key", "source_record_id", name="uq_source_record"),
)

checkpoints = Table(
    "checkpoints",
    metadata,
    Column("connector_id", String, primary_key=True),
    Column("account_key", String, primary_key=True),
    Column("cursor_value", Text, nullable=True),
)


class SQLiteEvidenceStore:
    """Single-writer SQLite adapter for one local vault."""

    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{database}")
        _configure_sqlite(self._engine)
        metadata.create_all(self._engine)

    @property
    def evidence_count(self) -> int:
        with self._engine.connect() as connection:
            return int(connection.scalar(select(func.count()).select_from(evidence)) or 0)

    def cursor_for(self, connector_id: str, account_key: str) -> SyncCursor | None:
        statement = select(checkpoints.c.cursor_value).where(
            checkpoints.c.connector_id == connector_id,
            checkpoints.c.account_key == account_key,
        )
        with self._engine.connect() as connection:
            value = connection.scalar(statement)
        return SyncCursor(value=value) if value is not None else None

    def transaction(self, connector_id: str, account_key: str) -> _SQLiteTransaction:
        return _SQLiteTransaction(self._engine, connector_id, account_key)

    def pragmas(self) -> dict[str, Any]:
        with self._engine.connect() as connection:
            return {
                "journal_mode": connection.exec_driver_sql("PRAGMA journal_mode").scalar_one(),
                "foreign_keys": connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one(),
                "busy_timeout": connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one(),
            }

    def close(self) -> None:
        self._engine.dispose()


class _SQLiteTransaction(EvidenceTransaction):
    def __init__(self, engine: Engine, connector_id: str, account_key: str) -> None:
        self._engine = engine
        self._connector_id = connector_id
        self._account_key = account_key
        self._connection: Connection | None = None
        self._transaction: RootTransaction | None = None

    async def __aenter__(self) -> _SQLiteTransaction:
        self._connection = self._engine.connect()
        self._transaction = self._connection.begin()
        return self

    async def put_evidence(self, identity: str, record: EvidenceRecord) -> bool:
        connection = self._require_connection()
        statement = (
            insert(evidence)
            .values(
                identity=identity,
                connector_id=self._connector_id,
                account_key=self._account_key,
                source_record_id=record.source_record_id,
                observed_at=record.observed_at,
                content_type=record.content_type,
                record_json=record.model_dump_json(),
            )
            .on_conflict_do_nothing(index_elements=["identity"])
        )
        result = connection.execute(statement)
        return result.rowcount == 1

    async def set_cursor(self, cursor: SyncCursor | None) -> None:
        connection = self._require_connection()
        statement = insert(checkpoints).values(
            connector_id=self._connector_id,
            account_key=self._account_key,
            cursor_value=cursor.value if cursor else None,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["connector_id", "account_key"],
            set_={"cursor_value": statement.excluded.cursor_value},
        )
        connection.execute(statement)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._transaction is None or self._connection is None:
            raise RuntimeError("SQLite transaction was not entered")
        try:
            if exc_type is None:
                self._transaction.commit()
            else:
                self._transaction.rollback()
        finally:
            self._connection.close()
        return False

    def _require_connection(self) -> Connection:
        if self._connection is None:
            raise RuntimeError("SQLite transaction was not entered")
        return self._connection


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()
