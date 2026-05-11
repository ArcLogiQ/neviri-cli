"""`neviri volume` subcommands.

Wraps ``/api/v1/block-storage/*``. Includes volumes (CRUD + attach/detach)
and snapshot management.

Note: the backend does NOT expose a volume resize endpoint, so this command
group has no ``resize`` action despite Story 5's draft acceptance criteria
mentioning one. Add when the backend ships ``POST /volumes/{id}/resize``.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from neviri_cli.client.block_storage import BlockStorageClient
from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error

volume_app = typer.Typer(
    name="volume",
    help="Manage block storage volumes and snapshots.",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> BlockStorageClient:
    return BlockStorageClient(make_client(ctx))


# ---------- volume CRUD ----------


@volume_app.command("list")
def list_volumes(
    ctx: typer.Context,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status (e.g. available, in-use)."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by name substring."),
    ] = None,
) -> None:
    """List block storage volumes.

    Example:

        neviri volume list
        neviri volume list --status available
    """
    try:
        emit(ctx, _client(ctx).list_volumes(status=status, name=name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("get")
def get_volume(
    ctx: typer.Context,
    volume_id: Annotated[str, typer.Argument(help="Volume ID.")],
) -> None:
    """Show details of a volume.

    Example:

        neviri volume get vol-abc
    """
    try:
        emit(ctx, _client(ctx).get_volume(volume_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("create")
def create_volume(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Volume name.")],
    size: Annotated[int, typer.Option("--size", "-S", help="Size in GB.", min=1)],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
    volume_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Volume type (e.g. ssd, hdd)."),
    ] = None,
    availability_zone: Annotated[
        str | None,
        typer.Option("--availability-zone", "-z", help="Availability zone."),
    ] = None,
    snapshot_id: Annotated[
        str | None,
        typer.Option("--from-snapshot", help="Create from snapshot ID."),
    ] = None,
) -> None:
    """Create a block storage volume.

    Example:

        neviri volume create data-01 --size 100
        neviri volume create restore-01 --size 50 --from-snapshot snap-xyz
    """
    body: dict[str, Any] = {"name": name, "size": size}
    if description:
        body["description"] = description
    if volume_type:
        body["volume_type"] = volume_type
    if availability_zone:
        body["availability_zone"] = availability_zone
    if snapshot_id:
        body["snapshot_id"] = snapshot_id

    try:
        emit(ctx, _client(ctx).create_volume(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("delete")
def delete_volume(
    ctx: typer.Context,
    volume_id: Annotated[str, typer.Argument(help="Volume ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a volume.

    Example:

        neviri volume delete vol-abc --yes
    """
    confirm_or_exit(f"Delete volume {volume_id}? This cannot be undone.", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_volume(volume_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- attach / detach ----------


@volume_app.command("attach")
def attach_volume(
    ctx: typer.Context,
    volume_id: Annotated[str, typer.Argument(help="Volume ID.")],
    server: Annotated[str, typer.Option("--server", "-s", help="Server ID to attach to.")],
    device: Annotated[
        str | None,
        typer.Option("--device", "-d", help="Device path on the server, e.g. /dev/vdb."),
    ] = None,
) -> None:
    """Attach a volume to a server.

    Example:

        neviri volume attach vol-abc --server srv-xyz --device /dev/vdb
    """
    try:
        emit(ctx, _client(ctx).attach_volume(volume_id, server, device=device))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("detach")
def detach_volume(
    ctx: typer.Context,
    volume_id: Annotated[str, typer.Argument(help="Volume ID.")],
    server: Annotated[str, typer.Option("--server", "-s", help="Server ID to detach from.")],
) -> None:
    """Detach a volume from a server.

    Example:

        neviri volume detach vol-abc --server srv-xyz
    """
    try:
        emit(ctx, _client(ctx).detach_volume(volume_id, server))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- snapshots ----------


@volume_app.command("snapshot")
def snapshot_volume(
    ctx: typer.Context,
    volume_id: Annotated[str, typer.Argument(help="Source volume ID.")],
    name: Annotated[str, typer.Option("--name", "-n", help="Snapshot name.")],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Snapshot description."),
    ] = None,
) -> None:
    """Create a snapshot of a volume.

    Example:

        neviri volume snapshot vol-abc --name daily-2026-05-10
    """
    body: dict[str, Any] = {"volume_id": volume_id, "name": name}
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).create_snapshot(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("snapshots")
def list_snapshots(
    ctx: typer.Context,
    volume_id: Annotated[
        str | None,
        typer.Option("--volume", "-v", help="Filter by source volume ID."),
    ] = None,
) -> None:
    """List volume snapshots.

    Example:

        neviri volume snapshots
        neviri volume snapshots --volume vol-abc
    """
    try:
        emit(ctx, _client(ctx).list_snapshots(volume_id=volume_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("snapshot-get")
def get_snapshot(
    ctx: typer.Context,
    snapshot_id: Annotated[str, typer.Argument(help="Snapshot ID.")],
) -> None:
    """Show details of a snapshot.

    Example:

        neviri volume snapshot-get snap-abc
    """
    try:
        emit(ctx, _client(ctx).get_snapshot(snapshot_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@volume_app.command("snapshot-delete")
def delete_snapshot(
    ctx: typer.Context,
    snapshot_id: Annotated[str, typer.Argument(help="Snapshot ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a snapshot.

    Example:

        neviri volume snapshot-delete snap-abc --yes
    """
    confirm_or_exit(f"Delete snapshot {snapshot_id}? This cannot be undone.", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_snapshot(snapshot_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
