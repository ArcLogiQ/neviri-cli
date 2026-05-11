"""`neviri object` subcommands.

Splits into two namespaces, matching proposal section 4.5:

    neviri object bucket {list|get|create|delete}
    neviri object {list|put|get|delete}

Buckets get the noun-style ``bucket`` subgroup; objects are flattened
because we're already under ``object``.
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

from neviri_cli.client.factory import make_client
from neviri_cli.client.object_storage import ObjectStorageClient
from neviri_cli.commands._common import confirm_or_exit, emit, get_cli_ctx
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error

object_app = typer.Typer(
    name="object",
    help="Manage S3-compatible object storage (buckets and objects).",
    no_args_is_help=True,
)

bucket_app = typer.Typer(
    name="bucket",
    help="Manage buckets (containers).",
    no_args_is_help=True,
)
object_app.add_typer(bucket_app, name="bucket")


def _client(ctx: typer.Context) -> ObjectStorageClient:
    return ObjectStorageClient(make_client(ctx))


def _parse_kv(items: list[str] | None) -> dict[str, str]:
    if not items:
        return {}
    result: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise UserError(f"--metadata expects KEY=VALUE, got: {item!r}")
        key, _, value = item.partition("=")
        result[key.strip()] = value
    return result


# ---------- bucket ops ----------


@bucket_app.command("list")
def list_buckets(ctx: typer.Context) -> None:
    """List buckets for the active account.

    Example:

        neviri object bucket list
    """
    try:
        emit(ctx, _client(ctx).list_buckets())
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@bucket_app.command("get")
def get_bucket(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name.")],
) -> None:
    """Show details of a bucket.

    Example:

        neviri object bucket get my-bucket
    """
    try:
        emit(ctx, _client(ctx).get_bucket(name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@bucket_app.command("create")
def create_bucket(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name (no slashes).")],
    metadata: Annotated[
        list[str] | None,
        typer.Option(
            "--metadata",
            "-m",
            help="Bucket metadata as KEY=VALUE. Repeatable.",
        ),
    ] = None,
) -> None:
    """Create a bucket.

    Example:

        neviri object bucket create backups -m env=prod -m owner=sre
    """
    try:
        emit(ctx, _client(ctx).create_bucket(name, metadata=_parse_kv(metadata)))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@bucket_app.command("delete")
def delete_bucket(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Bucket name.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a bucket. Must be empty.

    Example:

        neviri object bucket delete backups --yes
    """
    confirm_or_exit(f"Delete bucket {name}? It must already be empty.", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_bucket(name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- object ops ----------


@object_app.command("list")
def list_objects(
    ctx: typer.Context,
    bucket: Annotated[str, typer.Argument(help="Bucket name.")],
    prefix: Annotated[
        str | None,
        typer.Option("--prefix", "-p", help="Filter by object name prefix."),
    ] = None,
) -> None:
    """List objects in a bucket.

    Example:

        neviri object list backups --prefix 2026-05/
    """
    try:
        emit(ctx, _client(ctx).list_objects(bucket, prefix=prefix))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@object_app.command("put")
def put_object(
    ctx: typer.Context,
    bucket: Annotated[str, typer.Argument(help="Destination bucket.")],
    object_name: Annotated[str, typer.Argument(help="Object name (key) inside the bucket.")],
    file_path: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Local file to upload.",
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    content_type: Annotated[
        str | None,
        typer.Option("--content-type", "-t", help="MIME type. Default: application/octet-stream."),
    ] = None,
    no_progress: Annotated[
        bool,
        typer.Option(
            "--no-progress",
            help="Disable the progress bar (useful for non-TTY piping).",
        ),
    ] = False,
) -> None:
    """Upload a local file to a bucket.

    The CLI shows a byte-level progress bar by default. The backend buffers
    the upload in memory; multi-GB uploads are not recommended until Phase 3
    streaming support lands.

    Example:

        neviri object put backups db-2026-05-10.tar.gz --file ./db-2026-05-10.tar.gz
    """
    cli = get_cli_ctx(ctx)
    file_size = file_path.stat().st_size
    show_progress = not no_progress and not cli.no_color

    try:
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

                result = _client(ctx).upload_object(
                    bucket,
                    object_name,
                    file_path,
                    content_type=content_type,
                    on_progress=on_progress,
                )
        else:
            result = _client(ctx).upload_object(
                bucket, object_name, file_path, content_type=content_type
            )
        emit(ctx, result)
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@object_app.command("get")
def get_object(
    ctx: typer.Context,
    bucket: Annotated[str, typer.Argument(help="Source bucket.")],
    object_name: Annotated[str, typer.Argument(help="Object name (key).")],
    output_file: Annotated[
        Path,
        typer.Option(
            "--output-file",
            "-o",
            help="Local file path to write to.",
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ],
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Disable the progress bar."),
    ] = False,
) -> None:
    """Download an object to a local file.

    Example:

        neviri object get backups db-2026-05-10.tar.gz -o ./restore.tar.gz
    """
    cli = get_cli_ctx(ctx)
    # We don't know the size up-front (backend doesn't return Content-Length
    # to download_object), so we use an indeterminate spinner instead of a bar.
    show_progress = not no_progress and not cli.no_color

    try:
        if show_progress:
            with Progress(
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=Console(stderr=True, no_color=cli.no_color),
            ) as progress:
                task = progress.add_task(f"downloading {object_name}", total=None)

                def on_progress(n: int) -> None:
                    progress.update(task, advance=n)

                bytes_written = _client(ctx).download_object(
                    bucket, object_name, output_file, on_progress=on_progress
                )
        else:
            bytes_written = _client(ctx).download_object(bucket, object_name, output_file)
        emit(
            ctx,
            {
                "bucket": bucket,
                "object": object_name,
                "wrote": str(output_file),
                "bytes": bytes_written,
            },
        )
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@object_app.command("delete")
def delete_object(
    ctx: typer.Context,
    bucket: Annotated[str, typer.Argument(help="Bucket.")],
    object_name: Annotated[str, typer.Argument(help="Object name.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete an object from a bucket.

    Example:

        neviri object delete backups stale.tar.gz --yes
    """
    confirm_or_exit(
        f"Delete object {object_name} from bucket {bucket}? This cannot be undone.",
        yes=yes,
    )
    try:
        emit(ctx, _client(ctx).delete_object(bucket, object_name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
