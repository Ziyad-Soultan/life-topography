"""Operator CLI adapter."""

import typer

cli = typer.Typer(
    name="topography",
    help="Operate the local Life Topography vault.",
    no_args_is_help=True,
)


@cli.callback()
def root() -> None:
    """Keep a stable command-group interface as commands are added."""


@cli.command()
def doctor() -> None:
    """Report the honest readiness boundary of this build."""

    typer.echo("Life Topography pre-alpha backbone is installed.")
    typer.echo("Do not use real personal data yet.")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
