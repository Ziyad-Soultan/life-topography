"""Operator CLI adapter."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from life_topography.adapters.sqlite_store import SQLiteEvidenceStore
from life_topography.application.onboarding import OnboardingService
from life_topography.connectors.demo import OWNER_EMAIL, create_demo_mbox

cli = typer.Typer(
    name="topography",
    help="Operate the local Life Topography vault.",
    no_args_is_help=True,
)
_DEFAULT_DATABASE = Path(
    os.environ.get(
        "TOPOGRAPHY_DATABASE",
        Path.home() / ".local" / "share" / "life-topography" / "vault.db",
    )
)


@cli.callback()
def root() -> None:
    """Keep a stable command-group interface as commands are added."""


@cli.command()
def doctor() -> None:
    """Report the honest readiness boundary of this build."""

    typer.echo("Life Topography validation MVP is installed.")
    typer.echo("Local MBOX bootstrap and deterministic mapping are available.")
    typer.echo("Do not use real personal data unless the host disk is encrypted.")
    typer.echo("The SQLite vault is not application-level encrypted yet.")


@cli.command("import-mbox")
def import_mbox(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Local MBOX export to inspect.",
        ),
    ],
    owner_email: Annotated[
        str, typer.Option("--owner-email", help="Your email address in this export.")
    ],
    database: Annotated[
        Path, typer.Option("--database", help="Local SQLite vault path.")
    ] = _DEFAULT_DATABASE,
    i_understand_metadata_only: Annotated[
        bool,
        typer.Option(
            "--i-understand-metadata-only",
            help="Confirm local retention of email header metadata only.",
        ),
    ] = False,
) -> None:
    """Import email headers and build the initial evidence-backed map."""

    if not i_understand_metadata_only:
        typer.echo("Refusing import: --i-understand-metadata-only is required.", err=False)
        raise typer.Exit(code=2)
    store = SQLiteEvidenceStore(database)
    try:
        result = asyncio.run(
            OnboardingService(store).import_mbox(
                path,
                owner_email=owner_email,
                metadata_only_consent=True,
            )
        )
    finally:
        store.close()
    typer.echo(
        f"Imported {result.message_count} messages "
        f"({result.inserted} new, {result.existing} existing)."
    )
    typer.echo(f"Initial map: {result.node_count} nodes, {result.edge_count} relationships.")


@cli.command()
def demo(
    database: Annotated[
        Path, typer.Option("--database", help="Local SQLite vault path.")
    ] = _DEFAULT_DATABASE,
) -> None:
    """Build a fictional map through the real MBOX pipeline."""

    store = SQLiteEvidenceStore(database)
    try:
        if store.evidence_count:
            typer.echo("Refusing demo: the target vault already contains evidence.")
            raise typer.Exit(code=2)
        path = create_demo_mbox(database.parent / "demo.mbox")
        result = asyncio.run(
            OnboardingService(store).import_mbox(
                path,
                owner_email=OWNER_EMAIL,
                metadata_only_consent=True,
            )
        )
    finally:
        store.close()
    typer.echo(
        f"Synthetic map ready: {result.node_count} nodes, "
        f"{result.edge_count} relationships from {result.message_count} messages."
    )


@cli.command()
def serve(
    database: Annotated[
        Path, typer.Option("--database", help="Local SQLite vault path.")
    ] = _DEFAULT_DATABASE,
    host: Annotated[
        str, typer.Option(help="Bind address. Keep 127.0.0.1 unless you add auth.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8787,
) -> None:
    """Run the local onboarding and map interface."""

    from life_topography.api import create_app

    uvicorn.run(create_app(database), host=host, port=port)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
