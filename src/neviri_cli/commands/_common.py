"""Shared helpers for command modules."""

from __future__ import annotations

from typing import Any

import typer

from neviri_cli.context import CLIContext
from neviri_cli.output import render


def get_cli_ctx(ctx: typer.Context) -> CLIContext:
    """Return the typed CLIContext attached to ``ctx.obj`` by the root callback."""
    obj = ctx.obj
    assert isinstance(obj, CLIContext)
    return obj


def emit(ctx: typer.Context, data: Any) -> None:
    """Render ``data`` using the global --output / --no-color flags and print."""
    cli = get_cli_ctx(ctx)
    typer.echo(render(data, fmt=cli.output, no_color=cli.no_color))


def confirm_or_exit(prompt: str, *, yes: bool) -> None:
    """Interactive confirmation gate for destructive ops. Skipped when ``yes=True``."""
    if yes:
        return
    if not typer.confirm(prompt):
        typer.echo("Aborted.")
        raise typer.Exit(0)
