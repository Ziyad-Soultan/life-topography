import httpx
import pytest
from life_topography.api import app
from life_topography.cli import cli
from typer.testing import CliRunner


@pytest.mark.asyncio
async def test_health_endpoint_is_small_and_explicit() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "life-topography",
        "status": "ok",
        "stage": "pre-alpha",
    }


def test_doctor_warns_that_real_personal_data_is_unsafe() -> None:
    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "pre-alpha" in result.stdout
    assert "Do not use real personal data" in result.stdout
