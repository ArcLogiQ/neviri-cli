"""`neviri floating-ip` subcommands. Wraps `/api/v1/network/floating-ips/*`.

The backend's associate endpoint takes a port_id; in OpenStack-land that's the
network port attached to the server. The CLI exposes ``--port`` directly. If
you only have the server ID, run ``neviri vm get <server-id>`` and look up the
port in the response's ``addresses`` block.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from neviri_cli.client.factory import make_client
from neviri_cli.client.networking import NetworkingClient
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error

floating_ip_app = typer.Typer(
    name="floating-ip",
    help="Manage floating (public) IP addresses.",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> NetworkingClient:
    return NetworkingClient(make_client(ctx))


@floating_ip_app.command("list")
def list_floating_ips(
    ctx: typer.Context,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status (e.g. ACTIVE)."),
    ] = None,
) -> None:
    """List floating IPs.

    Example:

        neviri floating-ip list
    """
    try:
        emit(ctx, _client(ctx).list_floating_ips(status=status))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@floating_ip_app.command("get")
def get_floating_ip(
    ctx: typer.Context,
    floating_ip_id: Annotated[str, typer.Argument(help="Floating IP ID.")],
) -> None:
    """Show details of a floating IP.

    Example:

        neviri floating-ip get fip-abc
    """
    try:
        emit(ctx, _client(ctx).get_floating_ip(floating_ip_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@floating_ip_app.command("allocate")
def allocate_floating_ip(
    ctx: typer.Context,
    floating_network: Annotated[
        str,
        typer.Option(
            "--floating-network",
            "-N",
            help="External network ID to allocate the floating IP from.",
        ),
    ],
    subnet_id: Annotated[
        str | None,
        typer.Option("--subnet", help="Specific subnet to allocate from."),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
) -> None:
    """Allocate a floating IP from an external network.

    Example:

        neviri floating-ip allocate --floating-network ext-net-abc
    """
    body: dict[str, Any] = {"floating_network_id": floating_network}
    if subnet_id:
        body["subnet_id"] = subnet_id
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).allocate_floating_ip(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@floating_ip_app.command("release")
def release_floating_ip(
    ctx: typer.Context,
    floating_ip_id: Annotated[str, typer.Argument(help="Floating IP ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Release (delete) a floating IP.

    Example:

        neviri floating-ip release fip-abc --yes
    """
    confirm_or_exit(
        f"Release floating IP {floating_ip_id}? The address will return to the pool.",
        yes=yes,
    )
    try:
        emit(ctx, _client(ctx).release_floating_ip(floating_ip_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@floating_ip_app.command("associate")
def associate_floating_ip(
    ctx: typer.Context,
    floating_ip_id: Annotated[str, typer.Argument(help="Floating IP ID.")],
    port: Annotated[str, typer.Option("--port", "-p", help="Port ID to associate with.")],
) -> None:
    """Associate a floating IP with a port.

    Example:

        neviri floating-ip associate fip-abc --port port-xyz
    """
    try:
        emit(ctx, _client(ctx).associate_floating_ip(floating_ip_id, port))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@floating_ip_app.command("disassociate")
def disassociate_floating_ip(
    ctx: typer.Context,
    floating_ip_id: Annotated[str, typer.Argument(help="Floating IP ID.")],
) -> None:
    """Disassociate a floating IP from its port.

    Example:

        neviri floating-ip disassociate fip-abc
    """
    try:
        emit(ctx, _client(ctx).disassociate_floating_ip(floating_ip_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
