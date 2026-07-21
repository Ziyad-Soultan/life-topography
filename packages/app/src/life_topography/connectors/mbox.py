"""Metadata-only local MBOX connector."""

from __future__ import annotations

import hashlib
import json
import mailbox
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

from life_topography_sdk import (
    Capability,
    ConnectorManifest,
    EvidenceRecord,
    IngestBatch,
    SyncCursor,
    SyncMode,
)
from pydantic import JsonValue

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_REPLY_PREFIX = re.compile(r"^(?:(?:re|fw|fwd)\s*:\s*)+", re.IGNORECASE)
_CURSOR_PREFIX = "mbox-v1"


@dataclass(frozen=True, slots=True)
class MboxPreview:
    """Mutation-free summary shown before consent."""

    message_count: int
    valid_date_count: int
    invalid_date_count: int
    unique_address_count: int
    earliest: datetime | None
    latest: datetime | None
    file_size_bytes: int


class MboxConnector:
    """Read MBOX headers without retaining bodies or attachments."""

    manifest = ConnectorManifest(
        connector_id="mbox",
        display_name="Local MBOX",
        version="0.1.0",
        capabilities=frozenset(
            {Capability.METADATA, Capability.INCREMENTAL_SYNC, Capability.DELETION}
        ),
        supported_modes=frozenset({SyncMode.BOOTSTRAP, SyncMode.INCREMENTAL}),
    )

    def __init__(self, path: Path, *, owner_email: str, batch_size: int = 250) -> None:
        normalized_owner = _normalize_address(owner_email)
        if not normalized_owner:
            raise ValueError("valid owner email is required")
        if not path.is_file():
            raise ValueError("path must be a readable MBOX file")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.path = path
        self.owner_email = normalized_owner
        self.batch_size = batch_size
        self._source_fingerprint = _source_fingerprint(path)

    def preview(self) -> MboxPreview:
        box = mailbox.mbox(self.path, create=False)
        message_count = 0
        valid_dates: list[datetime] = []
        addresses: set[str] = set()
        try:
            for message in box:
                message_count += 1
                sent_at = _parse_date(message.get("Date"))
                if sent_at is not None:
                    valid_dates.append(sent_at)
                for participant in _participants(message):
                    address = participant["address"]
                    if isinstance(address, str):
                        addresses.add(address)
        finally:
            box.close()
        return MboxPreview(
            message_count=message_count,
            valid_date_count=len(valid_dates),
            invalid_date_count=message_count - len(valid_dates),
            unique_address_count=len(addresses),
            earliest=min(valid_dates) if valid_dates else None,
            latest=max(valid_dates) if valid_dates else None,
            file_size_bytes=self.path.stat().st_size,
        )

    def cursor_position(self, cursor: SyncCursor | None) -> int:
        """Return a display-only physical message position from an opaque cursor."""

        return _cursor_index(cursor, self._source_fingerprint)

    async def bootstrap(self, cursor: SyncCursor | None = None) -> AsyncIterator[IngestBatch]:
        start = self.cursor_position(cursor)
        box = mailbox.mbox(self.path, create=False)
        records: list[EvidenceRecord] = []
        seen_record_ids: set[str] = set()
        next_index = start
        try:
            for index, message in enumerate(box):
                record = _to_evidence(message)
                is_duplicate = record.source_record_id in seen_record_ids
                seen_record_ids.add(record.source_record_id)
                if index < start:
                    continue
                next_index = index + 1
                if len(records) == self.batch_size and not is_duplicate:
                    yield self._batch(records, index, SyncMode.BOOTSTRAP)
                    records = []
                if not is_duplicate:
                    records.append(record)
            if records:
                yield self._batch(records, next_index, SyncMode.BOOTSTRAP)
        finally:
            box.close()

    def changes(self, cursor: SyncCursor) -> AsyncIterator[IngestBatch]:
        """Read messages appended after a previously committed message index."""

        return self._changes(cursor)

    async def _changes(self, cursor: SyncCursor) -> AsyncIterator[IngestBatch]:
        async for batch in self.bootstrap(cursor):
            yield batch.model_copy(update={"mode": SyncMode.INCREMENTAL})

    def _batch(self, records: list[EvidenceRecord], next_index: int, mode: SyncMode) -> IngestBatch:
        return IngestBatch(
            connector_id=self.manifest.connector_id,
            account_key=self.owner_email,
            mode=mode,
            records=tuple(records),
            next_cursor=SyncCursor(
                value=f"{_CURSOR_PREFIX}:{self._source_fingerprint}:{next_index}"
            ),
        )


def _cursor_index(cursor: SyncCursor | None, source_fingerprint: str) -> int:
    if cursor is None:
        return 0
    if cursor.value.isdecimal():
        return int(cursor.value)
    try:
        prefix, cursor_fingerprint, raw_index = cursor.value.split(":", maxsplit=2)
        value = int(raw_index)
    except ValueError as error:
        raise ValueError("MBOX cursor must be a non-negative message index") from error
    if prefix != _CURSOR_PREFIX or value < 0:
        raise ValueError("MBOX cursor must be a non-negative message index")
    if cursor_fingerprint != source_fingerprint:
        return 0
    return value


def _source_fingerprint(path: Path) -> str:
    """Identify one physical MBOX state without exposing its path in the cursor."""

    stat = path.stat()
    material = "\0".join(
        (
            str(path.resolve()),
            str(stat.st_dev),
            str(stat.st_ino),
            str(stat.st_size),
            str(stat.st_mtime_ns),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _to_evidence(message: Message) -> EvidenceRecord:
    sent_at = _parse_date(message.get("Date"))
    subject = _decode(message.get("Subject"))
    sender = _first_participant([message.get("From", "")])
    recipients = _deduplicated_participants(
        [message.get("To", ""), message.get("Cc", ""), message.get("Bcc", "")]
    )
    recipients_payload: list[JsonValue] = [dict(participant) for participant in recipients]
    payload: dict[str, JsonValue] = {
        "kind": "email_headers",
        "message_id": _message_id(message),
        "sent_at": sent_at.isoformat() if sent_at else None,
        "date_valid": sent_at is not None,
        "subject": subject,
        "normalized_subject": _normalize_subject(subject),
        "sender": sender,
        "recipients": recipients_payload,
    }
    return EvidenceRecord(
        source_record_id=_source_record_id(message, payload),
        observed_at=sent_at or _EPOCH,
        content_type="application/vnd.life-topography.email-headers+json",
        payload=payload,
    )


def _source_record_id(message: Message, payload: dict[str, JsonValue]) -> str:
    message_id = _message_id(message)
    if message_id:
        return f"message-id:{message_id}"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"header-sha256:{digest}"


def _message_id(message: Message) -> str | None:
    value = message.get("Message-ID")
    if not value:
        return None
    normalized = value.strip().strip("<>").strip().lower()
    return normalized or None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (LookupError, UnicodeError):
        return value.strip()


def _normalize_subject(value: str) -> str:
    without_prefix = _REPLY_PREFIX.sub("", value.strip())
    return " ".join(without_prefix.casefold().split())


def _normalize_address(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.count("@") != 1:
        return ""
    local, domain = normalized.split("@", 1)
    if not local or not domain or "." not in domain:
        return ""
    return f"{local}@{domain}"


def _participants(message: Message) -> list[dict[str, JsonValue]]:
    return _deduplicated_participants(
        [
            message.get("From", ""),
            message.get("To", ""),
            message.get("Cc", ""),
            message.get("Bcc", ""),
        ]
    )


def _first_participant(values: Iterable[str]) -> dict[str, JsonValue] | None:
    participants = _deduplicated_participants(values)
    return participants[0] if participants else None


def _deduplicated_participants(values: Iterable[str]) -> list[dict[str, JsonValue]]:
    by_address: dict[str, dict[str, JsonValue]] = {}
    present_values = [value for value in values if value.strip()]
    for name, address in getaddresses(present_values):
        normalized = _normalize_address(address)
        if not normalized:
            continue
        decoded_name = _decode(name)
        existing = by_address.get(normalized)
        if existing is None or (not existing["name"] and decoded_name):
            by_address[normalized] = {"address": normalized, "name": decoded_name}
    return list(by_address.values())
