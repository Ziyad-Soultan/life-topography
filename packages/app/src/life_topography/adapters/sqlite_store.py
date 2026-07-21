"""SQLite evidence adapter with atomic evidence/cursor commits."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from life_topography_sdk import EvidenceRecord, SyncCursor
from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    event,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection
from sqlalchemy.engine.base import RootTransaction

from life_topography.domain.topography import (
    EdgeKind,
    EvidenceItem,
    NodeKind,
    TopographyEdge,
    TopographyNode,
    TopographySnapshot,
)
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

topography_nodes = Table(
    "topography_nodes",
    metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, nullable=False),
    Column("label", Text, nullable=False),
    Column("detail", Text, nullable=False),
    Column("activity_count", Integer, nullable=False),
    Column("first_seen", Text, nullable=True),
    Column("last_seen", Text, nullable=True),
    Column("derivation", String, nullable=False),
)

topography_edges = Table(
    "topography_edges",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "source_id", String, ForeignKey("topography_nodes.id", ondelete="CASCADE"), nullable=False
    ),
    Column(
        "target_id", String, ForeignKey("topography_nodes.id", ondelete="CASCADE"), nullable=False
    ),
    Column("kind", String, nullable=False),
    Column("weight", Integer, nullable=False),
    Column("first_seen", Text, nullable=True),
    Column("last_seen", Text, nullable=True),
    Column("derivation", String, nullable=False),
)

node_evidence = Table(
    "topography_node_evidence",
    metadata,
    Column(
        "node_id", String, ForeignKey("topography_nodes.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "evidence_identity",
        String,
        ForeignKey("evidence.identity", ondelete="CASCADE"),
        primary_key=True,
    ),
)

edge_evidence = Table(
    "topography_edge_evidence",
    metadata,
    Column(
        "edge_id", String, ForeignKey("topography_edges.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "evidence_identity",
        String,
        ForeignKey("evidence.identity", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SQLiteEvidenceStore:
    """Single-writer SQLite adapter for one local vault."""

    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self._database = database
        self._engine = create_engine(f"sqlite:///{database}")
        _configure_sqlite(self._engine, database)
        metadata.create_all(self._engine)
        _secure_database_files(database)

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

    def evidence_items(self) -> list[EvidenceItem]:
        statement = select(evidence.c.identity, evidence.c.record_json).order_by(
            evidence.c.identity
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).all()
        return [
            EvidenceItem(
                identity=row.identity,
                record=EvidenceRecord.model_validate_json(row.record_json),
            )
            for row in rows
        ]

    def replace_topography(self, snapshot: TopographySnapshot) -> None:
        with self._engine.begin() as connection:
            connection.execute(delete(edge_evidence))
            connection.execute(delete(node_evidence))
            connection.execute(delete(topography_edges))
            connection.execute(delete(topography_nodes))
            if snapshot.nodes:
                connection.execute(
                    topography_nodes.insert(),
                    [
                        {
                            "id": node.id,
                            "kind": node.kind.value,
                            "label": node.label,
                            "detail": node.detail,
                            "activity_count": node.activity_count,
                            "first_seen": _serialize_datetime(node.first_seen),
                            "last_seen": _serialize_datetime(node.last_seen),
                            "derivation": node.derivation,
                        }
                        for node in snapshot.nodes
                    ],
                )
                connection.execute(
                    node_evidence.insert(),
                    [
                        {"node_id": node.id, "evidence_identity": identity}
                        for node in snapshot.nodes
                        for identity in node.evidence_ids
                    ],
                )
            if snapshot.edges:
                connection.execute(
                    topography_edges.insert(),
                    [
                        {
                            "id": edge.id,
                            "source_id": edge.source_id,
                            "target_id": edge.target_id,
                            "kind": edge.kind.value,
                            "weight": edge.weight,
                            "first_seen": _serialize_datetime(edge.first_seen),
                            "last_seen": _serialize_datetime(edge.last_seen),
                            "derivation": edge.derivation,
                        }
                        for edge in snapshot.edges
                    ],
                )
                connection.execute(
                    edge_evidence.insert(),
                    [
                        {"edge_id": edge.id, "evidence_identity": identity}
                        for edge in snapshot.edges
                        for identity in edge.evidence_ids
                    ],
                )

    def load_topography(self) -> TopographySnapshot:
        with self._engine.connect() as connection:
            node_rows = connection.execute(
                select(topography_nodes).order_by(topography_nodes.c.kind, topography_nodes.c.id)
            ).mappings()
            edge_rows = connection.execute(
                select(topography_edges).order_by(topography_edges.c.id)
            ).mappings()
            node_links = _group_links(
                connection.execute(
                    select(node_evidence.c.node_id, node_evidence.c.evidence_identity)
                ).all()
            )
            edge_links = _group_links(
                connection.execute(
                    select(edge_evidence.c.edge_id, edge_evidence.c.evidence_identity)
                ).all()
            )
            nodes = tuple(
                TopographyNode(
                    id=row["id"],
                    kind=NodeKind(row["kind"]),
                    label=row["label"],
                    detail=row["detail"],
                    activity_count=row["activity_count"],
                    first_seen=_parse_datetime(row["first_seen"]),
                    last_seen=_parse_datetime(row["last_seen"]),
                    evidence_ids=tuple(sorted(node_links.get(row["id"], set()))),
                    derivation=row["derivation"],
                )
                for row in node_rows
            )
            edges = tuple(
                TopographyEdge(
                    id=row["id"],
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    kind=EdgeKind(row["kind"]),
                    weight=row["weight"],
                    first_seen=_parse_datetime(row["first_seen"]),
                    last_seen=_parse_datetime(row["last_seen"]),
                    evidence_ids=tuple(sorted(edge_links.get(row["id"], set()))),
                    derivation=row["derivation"],
                )
                for row in edge_rows
            )
        return TopographySnapshot(nodes=nodes, edges=edges)

    def reset(self) -> None:
        with self._engine.begin() as connection:
            connection.execute(delete(edge_evidence))
            connection.execute(delete(node_evidence))
            connection.execute(delete(topography_edges))
            connection.execute(delete(topography_nodes))
            connection.execute(delete(evidence))
            connection.execute(delete(checkpoints))
        with self._engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.exec_driver_sql("VACUUM")
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        _secure_database_files(self._database)

    def pragmas(self) -> dict[str, Any]:
        with self._engine.connect() as connection:
            return {
                "journal_mode": connection.exec_driver_sql("PRAGMA journal_mode").scalar_one(),
                "foreign_keys": connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one(),
                "busy_timeout": connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one(),
                "secure_delete": connection.exec_driver_sql("PRAGMA secure_delete").scalar_one(),
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


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _group_links(rows: Iterable[Any]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for object_id, evidence_identity in rows:
        grouped.setdefault(object_id, set()).add(evidence_identity)
    return grouped


def _configure_sqlite(engine: Engine, database: Path) -> None:
    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA secure_delete=ON")
        finally:
            cursor.close()
        _secure_database_files(database)


def _secure_database_files(database: Path) -> None:
    """Keep the vault and SQLite sidecars private to the current OS user."""

    for path in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
        if path.exists():
            path.chmod(0o600)
