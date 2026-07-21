from pathlib import Path

from life_topography.cli import cli
from life_topography.connectors.demo import create_demo_mbox
from typer.testing import CliRunner

runner = CliRunner()


def test_import_mbox_cli_requires_explicit_scope_confirmation(tmp_path: Path) -> None:
    mbox = create_demo_mbox(tmp_path / "demo.mbox")
    database = tmp_path / "vault.db"

    denied = runner.invoke(
        cli,
        [
            "import-mbox",
            str(mbox),
            "--owner-email",
            "alex@home.example",
            "--database",
            str(database),
        ],
    )
    accepted = runner.invoke(
        cli,
        [
            "import-mbox",
            str(mbox),
            "--owner-email",
            "alex@home.example",
            "--database",
            str(database),
            "--i-understand-metadata-only",
        ],
    )

    assert denied.exit_code != 0
    assert "metadata-only" in denied.stdout
    assert accepted.exit_code == 0, accepted.stdout
    assert "30 messages" in accepted.stdout
    assert "Initial map:" in accepted.stdout


def test_demo_cli_creates_a_testable_vault(tmp_path: Path) -> None:
    database = tmp_path / "vault.db"

    result = runner.invoke(cli, ["demo", "--database", str(database)])

    assert result.exit_code == 0, result.stdout
    assert database.exists()
    assert "Synthetic map ready" in result.stdout
