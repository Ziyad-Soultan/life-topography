from pathlib import Path

import pytest
from life_topography.adapters.sqlite_store import SQLiteEvidenceStore
from life_topography.application.onboarding import OnboardingService
from life_topography.connectors.demo import create_demo_mbox


@pytest.mark.asyncio
async def test_demo_uses_real_mbox_pipeline_and_builds_legible_map(tmp_path: Path) -> None:
    path = create_demo_mbox(tmp_path / "demo.mbox")
    store = SQLiteEvidenceStore(tmp_path / "vault.db")
    service = OnboardingService(store)

    preview = service.preview_mbox(path, owner_email="alex@home.example")
    result = await service.import_mbox(
        path,
        owner_email="alex@home.example",
        metadata_only_consent=True,
    )
    snapshot = service.topography()

    assert preview.message_count >= 20
    assert result.message_count == preview.message_count
    assert len([node for node in snapshot.nodes if node.kind.value == "person"]) >= 5
    assert len([node for node in snapshot.nodes if node.kind.value == "organization"]) >= 3
    assert len([node for node in snapshot.nodes if node.kind.value == "thread"]) >= 4
    assert all(
        item.record.payload.get("kind") == "email_headers" for item in store.evidence_items()
    )
    store.close()
