"""`neviri vm` subcommands: list / create / get / delete / start / stop /
reboot / resize / console (+ flavors / images list helpers).

Wraps ``/api/v1/compute/servers/*`` per ADR 0001. Console prints the noVNC URL
returned by the backend - it does NOT proxy a serial connection.
"""

from __future__ import annotations

import webbrowser
from typing import Annotated, Any

import typer

from neviri_cli.client.compute import ComputeClient
from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error

vm_app = typer.Typer(
    name="vm",
    help="Manage virtual machines.",
    no_args_is_help=True,
)


def _compute(ctx: typer.Context) -> ComputeClient:
    return ComputeClient(make_client(ctx))


# ---------- read commands ----------


@vm_app.command("list")
def list_vms(
    ctx: typer.Context,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status (e.g. ACTIVE, SHUTOFF)."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by name substring."),
    ] = None,
) -> None:
    """List virtual machines.

    Example:

        neviri vm list
        neviri vm list --status ACTIVE
        neviri vm list -o json
    """
    try:
        servers = _compute(ctx).list_servers(status=status, name=name)
        emit(ctx, servers)
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("get")
def get_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
) -> None:
    """Show details of a virtual machine.

    Example:

        neviri vm get abc-123
    """
    try:
        emit(ctx, _compute(ctx).get_server(server_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("flavors")
def list_flavors(ctx: typer.Context) -> None:
    """List available flavors (instance types).

    Example:

        neviri vm flavors
    """
    try:
        emit(ctx, _compute(ctx).list_flavors())
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("images")
def list_images(ctx: typer.Context) -> None:
    """List available images.

    Example:

        neviri vm images
    """
    try:
        emit(ctx, _compute(ctx).list_images())
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- create ----------


@vm_app.command("create")
def create_vm(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name.")],
    flavor: Annotated[str, typer.Option("--flavor", "-f", help="Flavor (instance type) ID.")],
    image: Annotated[str, typer.Option("--image", "-i", help="Image (OS) ID.")],
    network: Annotated[str, typer.Option("--network", "-N", help="Network ID to attach.")],
    key_name: Annotated[
        str | None,
        typer.Option("--key-name", "-k", help="SSH key pair name."),
    ] = None,
    security_group: Annotated[
        list[str] | None,
        typer.Option(
            "--security-group",
            "-g",
            help="Security group name. Repeatable. Defaults to ['default'].",
        ),
    ] = None,
    availability_zone: Annotated[
        str | None,
        typer.Option("--availability-zone", "-z", help="Availability zone."),
    ] = None,
) -> None:
    """Create a virtual machine.

    Example:

        neviri vm create web-01 \\
            --flavor m1.small --image ubuntu-22.04 --network default
    """
    body: dict[str, Any] = {
        "name": name,
        "flavor_id": flavor,
        "image_id": image,
        "network_id": network,
    }
    if key_name:
        body["key_name"] = key_name
    if security_group:
        body["security_groups"] = security_group
    if availability_zone:
        body["availability_zone"] = availability_zone

    try:
        emit(ctx, _compute(ctx).create_server(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- destructive ----------


@vm_app.command("delete")
def delete_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Force-delete even if the server is in an error state."),
    ] = False,
) -> None:
    """Delete a virtual machine.

    Example:

        neviri vm delete abc-123 --yes
    """
    confirm_or_exit(f"Delete VM {server_id}? This cannot be undone.", yes=yes)
    try:
        emit(ctx, _compute(ctx).delete_server(server_id, force=force))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- power actions ----------


@vm_app.command("start")
def start_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
) -> None:
    """Start a stopped VM.

    Example:

        neviri vm start abc-123
    """
    try:
        emit(ctx, _compute(ctx).server_action(server_id, "start"))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("stop")
def stop_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
) -> None:
    """Stop a running VM.

    Example:

        neviri vm stop abc-123
    """
    try:
        emit(ctx, _compute(ctx).server_action(server_id, "stop"))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("reboot")
def reboot_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
    hard: Annotated[
        bool,
        typer.Option("--hard", help="Hard reboot (power-cycle). Default is SOFT."),
    ] = False,
) -> None:
    """Reboot a VM. Defaults to a soft reboot; pass --hard to power-cycle.

    Example:

        neviri vm reboot abc-123
        neviri vm reboot abc-123 --hard
    """
    try:
        emit(
            ctx,
            _compute(ctx).server_action(
                server_id, "reboot", reboot_type="HARD" if hard else "SOFT"
            ),
        )
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- resize ----------


@vm_app.command("resize")
def resize_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
    flavor: Annotated[
        str,
        typer.Option("--flavor", "-f", help="Target flavor (instance type) ID."),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the downtime confirmation prompt."),
    ] = False,
) -> None:
    """Resize a VM to a new flavor.

    The VM enters VERIFY_RESIZE; you must then run `neviri vm resize-confirm`
    or `neviri vm resize-revert`.

    Example:

        neviri vm resize abc-123 --flavor m1.large
    """
    confirm_or_exit(
        f"Resize VM {server_id} to flavor {flavor}? This will cause a brief downtime.",
        yes=yes,
    )
    try:
        emit(ctx, _compute(ctx).resize_server(server_id, flavor))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("resize-confirm")
def resizeconfirm_or_exit(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
) -> None:
    """Confirm a pending resize on a VM.

    Example:

        neviri vm resize-confirm abc-123
    """
    try:
        emit(ctx, _compute(ctx).confirm_resize(server_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@vm_app.command("resize-revert")
def resize_revert(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
) -> None:
    """Revert a pending resize on a VM.

    Example:

        neviri vm resize-revert abc-123
    """
    try:
        emit(ctx, _compute(ctx).revert_resize(server_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- console ----------


@vm_app.command("console")
def console_vm(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID.")],
    console_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Console type: novnc (default), xvpvnc, or spice-html5.",
            case_sensitive=False,
        ),
    ] = "novnc",
    launch: Annotated[
        bool,
        typer.Option("--launch", help="Open the console URL in the default browser."),
    ] = False,
) -> None:
    """Print (and optionally launch) the VM's noVNC/SPICE console URL.

    Example:

        neviri vm console abc-123
        neviri vm console abc-123 --launch
    """
    try:
        result = _compute(ctx).get_console(server_id, console_type=console_type)
        url = result.get("url")
        if not isinstance(url, str) or not url:
            raise UserError("backend did not return a console URL")
        typer.echo(url)
        if launch:
            webbrowser.open(url)
    except NeviriCLIError as exc:
        handle_cli_error(exc)
