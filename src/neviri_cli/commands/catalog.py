"""Catalog operations supported by explicit IAM and legacy profiles."""

from __future__ import annotations

from typing import Annotated

import typer

from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error

catalog_app = typer.Typer(
    name="catalog", help="Inspect catalog app releases.", no_args_is_help=True
)


@catalog_app.callback()
def catalog() -> None:
    """Catalog operations."""


@catalog_app.command("release-status")
def release_status(ctx: typer.Context, release_id: Annotated[int, typer.Argument(min=1)]) -> None:
    """Read release status; the API verifies account scope and IAM policies."""
    try:
        with make_client(ctx) as client:
            emit(ctx, client.get(f"/api/v1/catalog/releases/{release_id}/status"))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
