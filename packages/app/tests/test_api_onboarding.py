from __future__ import annotations

import asyncio
import mailbox
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from life_topography.api import create_app


def create_mbox(path: Path) -> Path:
    box = mailbox.mbox(path, create=True)
    for index, (sender, recipient, subject) in enumerate(
        [
            ("ada@analytical.engine", "owner@example.net", "Engine roadmap"),
            ("owner@example.net", "grace@gmail.com", "Re: Engine roadmap"),
        ],
        start=1,
    ):
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Date"] = f"Mon, {index:02d} Jun 2026 10:00:00 +0000"
        message["Message-ID"] = f"<{index}@example.test>"
        message.set_content("PRIVATE BODY")
        box.add(message)
    box.flush()
    box.close()
    return path


@pytest.mark.asyncio
async def test_local_onboarding_journey(tmp_path: Path) -> None:
    app = create_app(tmp_path / "vault.db")
    transport = httpx.ASGITransport(app=app)
    path = create_mbox(tmp_path / "mail.mbox")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        page = await client.get("/")
        assert page.status_code == 200
        assert "Map your history" in page.text
        assert "https://" not in page.text

        preview = await client.post(
            "/api/onboarding/preview",
            json={"path": str(path), "owner_email": "owner@example.net"},
        )
        assert preview.status_code == 200
        assert preview.headers["cache-control"] == "no-store"
        assert preview.json()["message_count"] == 2

        denied = await client.post(
            "/api/onboarding/import",
            json={
                "path": str(path),
                "owner_email": "owner@example.net",
                "metadata_only_consent": False,
            },
        )
        assert denied.status_code == 403

        started = await client.post(
            "/api/onboarding/import",
            json={
                "path": str(path),
                "owner_email": "owner@example.net",
                "metadata_only_consent": True,
            },
        )
        assert started.status_code == 202
        job_id = started.json()["job_id"]

        job: dict[str, object] = {"status": "queued"}
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}")).json()
            if job["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.01)
        assert job["status"] == "completed", job
        assert job["current"] == 2
        assert job["total"] == 2

        topology = (await client.get("/api/topography")).json()
        assert topology["summary"]["people"] == 2
        assert topology["summary"]["threads"] == 1
        assert topology["nodes"]
        assert topology["edges"]

        evidence_id = topology["nodes"][0]["evidence_ids"][0]
        evidence = await client.get(f"/api/evidence/{quote(evidence_id, safe='')}")
        assert evidence.status_code == 200
        assert evidence.json()["payload"]["kind"] == "email_headers"
        assert "PRIVATE BODY" not in evidence.text

        refused_reset = await client.request("DELETE", "/api/vault", json={"confirmation": "no"})
        assert refused_reset.status_code == 400
        reset = await client.request("DELETE", "/api/vault", json={"confirmation": "DELETE MY MAP"})
        assert reset.status_code == 204
        assert (await client.get("/api/topography")).json()["nodes"] == []
        assert (await client.get(f"/api/jobs/{job_id}")).status_code == 404


@pytest.mark.asyncio
async def test_demo_endpoint_uses_same_import_pipeline(tmp_path: Path) -> None:
    app = create_app(tmp_path / "vault.db")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        started = await client.post("/api/demo")
        assert started.status_code == 202
        job_id = started.json()["job_id"]
        job: dict[str, object] = {"status": "queued"}
        for _ in range(100):
            job = (await client.get(f"/api/jobs/{job_id}")).json()
            if job["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.01)
        assert job["status"] == "completed", job
        topology = (await client.get("/api/topography")).json()
        assert topology["summary"]["people"] >= 5
        assert topology["summary"]["organizations"] >= 3


@pytest.mark.asyncio
async def test_api_errors_are_bounded_and_do_not_echo_paths(tmp_path: Path) -> None:
    app = create_app(tmp_path / "vault.db")
    transport = httpx.ASGITransport(app=app)
    secret_path = tmp_path / "private" / "missing.mbox"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/onboarding/preview",
            json={"path": str(secret_path), "owner_email": "owner@example.net"},
        )

    assert response.status_code == 400
    assert str(secret_path) not in response.text
    assert response.json() == {"detail": "Unable to read that MBOX file."}


@pytest.mark.asyncio
async def test_browser_import_is_confined_to_declared_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "imports"
    allowed.mkdir()
    outside = create_mbox(tmp_path / "outside.mbox")
    app = create_app(tmp_path / "vault.db", import_roots=(allowed,))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/onboarding/preview",
            json={"path": str(outside), "owner_email": "owner@example.net"},
        )

    assert response.status_code == 400
    assert str(outside) not in response.text


@pytest.mark.asyncio
async def test_untrusted_host_is_rejected(tmp_path: Path) -> None:
    app = create_app(tmp_path / "vault.db")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://attacker.invalid") as client:
        response = await client.get("/health")

    assert response.status_code == 400
