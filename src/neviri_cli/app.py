"""Typer root application for the Neviri CLI."""

from typing import Annotated

import typer

from neviri_cli import __version__

app = typer.Typer(
    name="neviri",
    help="Official command-line interface for the Neviri Cloud Platform.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"neviri {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Neviri CLI."""
