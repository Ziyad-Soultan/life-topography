from __future__ import annotations

import mailbox
from email.message import EmailMessage
from pathlib import Path

import pytest
from life_topography.adapters.sqlite_store import SQLiteEvidenceStore
from life_topography.application.onboarding import ImportPhase, OnboardingService


def create_mbox(path: Path) -> Path:
    box = mailbox.mbox(path, create=True)
    for index, (sender, recipient, subject) in enumerate(
        [
            ("ada@analytical.engine", "owner@example.net", "Engine"),
            ("owner@example.net", "grace@gmail.com", "Re: Engine"),
        ],
        start=1,
    ):
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Date"] = f"Mon, {index:02d} Jun 2026 10:00:00 +0000"
        message["Message-ID"] = f"<{index}@example.test>"
        message.set_content(f"BODY {index} MUST NOT PERSIST")
        box.add(message)
    box.flush()
    box.close()
    return path


def test_preview_does_not_mutate_vault(tmp_path: Path) -> None:
    store = SQLiteEvidenceStore(tmp_path / "vault.db")
    service = OnboardingService(store)

    preview = service.preview_mbox(
        create_mbox(tmp_path / "mail.mbox"), owner_email="owner@example.net"
    )

    assert preview.message_count == 2
    assert store.evidence_count == 0
    assert store.load_topography().nodes == ()
    store.close()


@pytest.mark.asyncio
async def test_import_requires_explicit_metadata_only_consent(tmp_path: Path) -> None:
    store = SQLiteEvidenceStore(tmp_path / "vault.db")
    service = OnboardingService(store)

    with pytest.raises(PermissionError, match="metadata-only consent"):
        await service.import_mbox(
            create_mbox(tmp_path / "mail.mbox"),
            owner_email="owner@example.net",
            metadata_only_consent=False,
        )

    assert store.evidence_count == 0
    store.close()


@pytest.mark.asyncio
async def test_import_builds_map_reports_progress_and_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteEvidenceStore(tmp_path / "vault.db")
    service = OnboardingService(store)
    path = create_mbox(tmp_path / "mail.mbox")
    progress: list[tuple[ImportPhase, int, int]] = []

    first = await service.import_mbox(
        path,
        owner_email="owner@example.net",
        metadata_only_consent=True,
        progress=lambda phase, current, total: progress.append((phase, current, total)),
    )
    second = await service.import_mbox(
        path,
        owner_email="owner@example.net",
        metadata_only_consent=True,
    )

    assert first.inserted == 2
    assert first.message_count == 2
    assert first.node_count >= 4
    assert first.edge_count >= 4
    assert second.inserted == 0
    assert store.evidence_count == 2
    assert progress[0] == (ImportPhase.IMPORTING, 0, 2)
    assert (ImportPhase.PROJECTING, 2, 2) in progress
    assert progress[-1] == (ImportPhase.COMPLETED, 2, 2)
    persisted = " ".join(item.record.model_dump_json() for item in store.evidence_items())
    assert "MUST NOT PERSIST" not in persisted
    store.close()


@pytest.mark.asyncio
async def test_reset_forgets_everything(tmp_path: Path) -> None:
    store = SQLiteEvidenceStore(tmp_path / "vault.db")
    service = OnboardingService(store)
    await service.import_mbox(
        create_mbox(tmp_path / "mail.mbox"),
        owner_email="owner@example.net",
        metadata_only_consent=True,
    )

    service.reset()

    assert store.evidence_count == 0
    assert service.topography().nodes == ()
    assert service.topography().edges == ()
    store.close()
