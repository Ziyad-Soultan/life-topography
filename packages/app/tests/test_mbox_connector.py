from __future__ import annotations

import mailbox
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

import pytest
from life_topography.connectors.mbox import MboxConnector
from life_topography_sdk import IngestBatch, SyncCursor


def add_message(
    box: mailbox.mbox,
    *,
    sender: str,
    to: str,
    subject: str,
    date: str | None,
    message_id: str | None,
    body: str,
    cc: str | None = None,
) -> None:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    if cc:
        message["Cc"] = cc
    message["Subject"] = subject
    if date:
        message["Date"] = date
    if message_id:
        message["Message-ID"] = message_id
    message.set_content(body)
    box.add(message)


@pytest.fixture
def sample_mbox(tmp_path: Path) -> Path:
    path = tmp_path / "mail.mbox"
    box = mailbox.mbox(path, create=True)
    add_message(
        box,
        sender='"Ada Lovelace" <ADA@example.com>',
        to="owner@example.net",
        subject="Project Engine",
        date="Mon, 01 Jun 2026 10:00:00 +0000",
        message_id="<one@example.com>",
        body="CLASSIFIED BODY ONE",
    )
    add_message(
        box,
        sender="owner@example.net",
        to='"Ada Lovelace" <ada@example.com>, grace@example.org',
        cc="ada@example.com",
        subject="Re: Project Engine",
        date="Tue, 02 Jun 2026 11:30:00 +0000",
        message_id="<two@example.net>",
        body="CLASSIFIED BODY TWO",
    )
    add_message(
        box,
        sender="malformed",
        to="owner@example.net",
        subject="No usable date",
        date=None,
        message_id=None,
        body="CLASSIFIED BODY THREE",
    )
    box.flush()
    box.close()
    return path


async def collect(stream: AsyncIterator[IngestBatch]) -> list[IngestBatch]:
    return [batch async for batch in stream]


def test_preview_is_read_only_and_reports_scope(sample_mbox: Path) -> None:
    connector = MboxConnector(sample_mbox, owner_email="OWNER@example.net")

    preview = connector.preview()

    assert preview.message_count == 3
    assert preview.valid_date_count == 2
    assert preview.invalid_date_count == 1
    assert preview.unique_address_count == 3
    assert preview.earliest == datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    assert preview.latest == datetime(2026, 6, 2, 11, 30, tzinfo=UTC)
    assert preview.file_size_bytes == sample_mbox.stat().st_size
    assert sample_mbox.read_bytes().count(b"CLASSIFIED BODY") == 3


@pytest.mark.asyncio
async def test_bootstrap_retains_headers_only_and_normalizes_participants(
    sample_mbox: Path,
) -> None:
    connector = MboxConnector(sample_mbox, owner_email="owner@example.net", batch_size=2)

    batches = await collect(connector.bootstrap())

    assert len(batches[0].records) == 2
    assert len(batches[1].records) == 1
    assert batches[0].next_cursor is not None
    assert batches[1].next_cursor is not None
    assert batches[0].next_cursor.value.endswith(":2")
    assert batches[1].next_cursor.value.endswith(":3")
    assert batches[0].next_cursor != batches[1].next_cursor
    first = batches[0].records[0]
    second = batches[0].records[1]
    assert first.source_record_id == "message-id:one@example.com"
    assert first.payload["sender"] == {
        "address": "ada@example.com",
        "name": "Ada Lovelace",
    }
    assert second.payload["recipients"] == [
        {"address": "ada@example.com", "name": "Ada Lovelace"},
        {"address": "grace@example.org", "name": ""},
    ]
    assert first.payload["normalized_subject"] == "project engine"
    assert second.payload["normalized_subject"] == "project engine"

    serialized = " ".join(record.model_dump_json() for batch in batches for record in batch.records)
    assert "CLASSIFIED BODY" not in serialized
    assert "body" not in serialized.lower()


@pytest.mark.asyncio
async def test_resume_and_fallback_identity_are_deterministic(sample_mbox: Path) -> None:
    first = MboxConnector(sample_mbox, owner_email="owner@example.net", batch_size=2)
    second = MboxConnector(sample_mbox, owner_email="owner@example.net", batch_size=2)

    first_run = await collect(first.bootstrap())
    resumed = await collect(second.bootstrap(SyncCursor(value="2")))
    repeat = await collect(second.bootstrap())

    assert len(resumed) == 1
    assert resumed[0].records[0].source_record_id.startswith("header-sha256:")
    assert resumed[0].records[0].source_record_id == repeat[1].records[0].source_record_id
    assert first_run[1].records[0].observed_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert first_run[1].records[0].payload["date_valid"] is False


@pytest.mark.asyncio
async def test_cursor_from_another_mbox_does_not_skip_same_owner_messages(tmp_path: Path) -> None:
    first_path = tmp_path / "first.mbox"
    first_box = mailbox.mbox(first_path, create=True)
    add_message(
        first_box,
        sender="sender@example.com",
        to="owner@example.net",
        subject="First export",
        date="Mon, 01 Jun 2026 10:00:00 +0000",
        message_id="<shared@example.com>",
        body="FIRST EXPORT BODY",
    )
    first_box.flush()
    first_box.close()
    second_path = tmp_path / "second.mbox"
    second_box = mailbox.mbox(second_path, create=True)
    add_message(
        second_box,
        sender="sender@example.com",
        to="owner@example.net",
        subject="Same message in another export",
        date="Mon, 01 Jun 2026 10:00:00 +0000",
        message_id="<shared@example.com>",
        body="SECOND EXPORT SHARED BODY",
    )
    add_message(
        second_box,
        sender="other@example.com",
        to="owner@example.net",
        subject="Only in second export",
        date="Tue, 02 Jun 2026 10:00:00 +0000",
        message_id="<second@example.com>",
        body="SECOND EXPORT UNIQUE BODY",
    )
    second_box.flush()
    second_box.close()

    first_batches = await collect(
        MboxConnector(first_path, owner_email="owner@example.net").bootstrap()
    )
    second_batches = await collect(
        MboxConnector(second_path, owner_email="owner@example.net").bootstrap(
            first_batches[-1].next_cursor
        )
    )

    assert [record.source_record_id for record in second_batches[0].records] == [
        "message-id:shared@example.com",
        "message-id:second@example.com",
    ]
    assert first_batches[0].account_key == second_batches[0].account_key == "owner@example.net"
    assert (
        first_batches[0].records[0].source_record_id
        == second_batches[0].records[0].source_record_id
    )


@pytest.mark.asyncio
async def test_source_aware_cursor_resumes_the_same_mbox(sample_mbox: Path) -> None:
    connector = MboxConnector(sample_mbox, owner_email="owner@example.net", batch_size=1)
    first_batches = await collect(connector.bootstrap())

    assert first_batches[0].next_cursor is not None
    assert not first_batches[0].next_cursor.value.isdecimal()

    resumed = await collect(connector.bootstrap(first_batches[0].next_cursor))

    assert [record.source_record_id for batch in resumed for record in batch.records] == [
        "message-id:two@example.net",
        first_batches[2].records[0].source_record_id,
    ]
    assert resumed[-1].next_cursor == first_batches[-1].next_cursor


@pytest.mark.asyncio
async def test_replaced_mbox_at_same_path_restarts_physical_scan(tmp_path: Path) -> None:
    path = tmp_path / "replaceable.mbox"
    first_box = mailbox.mbox(path, create=True)
    add_message(
        first_box,
        sender="first@example.com",
        to="owner@example.net",
        subject="First source state",
        date="Mon, 01 Jun 2026 10:00:00 +0000",
        message_id="<first@example.com>",
        body="FIRST BODY",
    )
    first_box.flush()
    first_box.close()
    first_batches = await collect(MboxConnector(path, owner_email="owner@example.net").bootstrap())
    cursor = first_batches[-1].next_cursor

    path.unlink()
    replacement = mailbox.mbox(path, create=True)
    for index in range(2):
        add_message(
            replacement,
            sender=f"replacement-{index}@example.com",
            to="owner@example.net",
            subject=f"Replacement {index}",
            date="Tue, 02 Jun 2026 10:00:00 +0000",
            message_id=f"<replacement-{index}@example.com>",
            body=f"REPLACEMENT BODY {index}",
        )
    replacement.flush()
    replacement.close()

    batches = await collect(MboxConnector(path, owner_email="owner@example.net").bootstrap(cursor))

    assert [record.source_record_id for batch in batches for record in batch.records] == [
        "message-id:replacement-0@example.com",
        "message-id:replacement-1@example.com",
    ]


@pytest.mark.asyncio
async def test_duplicate_message_ids_are_skipped_across_physical_resume_index(
    tmp_path: Path,
) -> None:
    path = tmp_path / "duplicates.mbox"
    box = mailbox.mbox(path, create=True)
    for subject, message_id in (
        ("Original", "<duplicate@example.com>"),
        ("Unique", "<unique@example.com>"),
        ("Duplicate", "<duplicate@example.com>"),
    ):
        add_message(
            box,
            sender="sender@example.com",
            to="owner@example.net",
            subject=subject,
            date="Mon, 01 Jun 2026 10:00:00 +0000",
            message_id=message_id,
            body=f"{subject} body",
        )
    box.flush()
    box.close()
    connector = MboxConnector(path, owner_email="owner@example.net", batch_size=10)

    batches = await collect(connector.bootstrap())
    resumed = await collect(connector.bootstrap(SyncCursor(value="1")))

    assert [record.source_record_id for record in batches[0].records] == [
        "message-id:duplicate@example.com",
        "message-id:unique@example.com",
    ]
    assert [record.source_record_id for record in resumed[0].records] == [
        "message-id:unique@example.com"
    ]
    assert resumed[0].next_cursor == batches[0].next_cursor


def test_preview_rejects_missing_or_non_file_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="readable MBOX file"):
        MboxConnector(tmp_path / "missing.mbox", owner_email="owner@example.net")

    with pytest.raises(ValueError, match="valid owner email"):
        MboxConnector(tmp_path, owner_email="not-an-email")
