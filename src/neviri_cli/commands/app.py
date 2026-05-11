"""`neviri app` subcommands.

Wraps ``/api/v1/apps/*``. App lifecycle, ZIP upload (which creates a
deployment), and env-var management.

Note: the backend has no logs or restart endpoint for apps - those AC items
in Story 11 require backend changes and are intentionally omitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from neviri_cli.client.deployment import DeploymentClient
from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import confirm_or_exit, emit, get_cli_ctx
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error

app_app = typer.Typer(
    name="app",
    help="Manage applications (uploads, deployments, env vars).",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> DeploymentClient:
    return DeploymentClient(make_client(ctx))


@app_app.command("list")
def list_apps(ctx: typer.Context) -> None:
    """List apps for the active account.

    Example:

        neviri app list
    """
    try:
        emit(ctx, _client(ctx).list_apps())
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("get")
def get_app(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
) -> None:
    """Show details of an app."""
    try:
        emit(ctx, _client(ctx).get_app(app_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("create")
def create_app(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="App name.")],
) -> None:
    """Create a new app.

    Example:

        neviri app create my-web
    """
    try:
        emit(ctx, _client(ctx).create_app(name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("delete")
def delete_app(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete an app and all of its resources."""
    confirm_or_exit(
        f"Delete app {app_id} and ALL its deployments + env vars? This cannot be undone.",
        yes=yes,
    )
    try:
        emit(ctx, _client(ctx).delete_app(app_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("deployments")
def list_app_deployments(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
) -> None:
    """List deployments for an app.

    Example:

        neviri app deployments 42
    """
    try:
        emit(ctx, _client(ctx).list_deployments(app_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("upload")
def upload_app(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
    file_path: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Local .zip file to upload.",
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    no_progress: Annotated[
        bool, typer.Option("--no-progress", help="Disable the progress bar.")
    ] = False,
) -> None:
    """Upload a ZIP and create a new deployment.

    The deployment starts in ``pending`` and needs ``neviri deploy build`` /
    ``neviri deploy deploy`` / ``service`` / ``ingress`` (or
    ``neviri deploy run``) to progress through the 4 stages.

    Example:

        neviri app upload 42 --file ./my-app.zip
    """
    cli = get_cli_ctx(ctx)
    show_progress = not no_progress and not cli.no_color
    file_size = file_path.stat().st_size

    try:
        if file_path.suffix.lower() != ".zip":
            raise UserError(f"upload expects a .zip file, got {file_path.suffix}")
        if show_progress:
            with Progress(
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=Console(stderr=True, no_color=cli.no_color),
            ) as progress:
                task = progress.add_task(f"uploading {file_path.name}", total=file_size)

                def on_progress(n: int) -> None:
                    progress.update(task, advance=n)

                result = _client(ctx).upload_zip(app_id, file_path, on_progress=on_progress)
        else:
            result = _client(ctx).upload_zip(app_id, file_path)
        emit(ctx, result)
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- env vars ----------


@app_app.command("env-list")
def list_env(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
) -> None:
    """List environment variables for an app."""
    try:
        emit(ctx, _client(ctx).list_env_variables(app_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("env-set")
def set_env(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
    pair: Annotated[str, typer.Argument(help="KEY=VALUE.")],
) -> None:
    """Set an environment variable.

    Example:

        neviri app env-set 42 DATABASE_URL=postgres://...
    """
    try:
        if "=" not in pair:
            raise UserError("expected KEY=VALUE")
        key, _, value = pair.partition("=")
        if not key:
            raise UserError("KEY cannot be empty")
        emit(ctx, _client(ctx).add_env_variable(app_id, key, value))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@app_app.command("env-unset")
def unset_env(
    ctx: typer.Context,
    app_id: Annotated[int, typer.Argument(help="App ID.")],
    env_id: Annotated[int, typer.Argument(help="Env variable ID.")],
) -> None:
    """Delete an environment variable.

    Example:

        neviri app env-unset 42 7
    """
    try:
        emit(ctx, _client(ctx).delete_env_variable(app_id, env_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
