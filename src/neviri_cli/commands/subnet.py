"""`neviri subnet` subcommands. Wraps `/api/v1/network/subnets/*`."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from neviri_cli.client.factory import make_client
from neviri_cli.client.networking import NetworkingClient
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error

subnet_app = typer.Typer(
    name="subnet",
    help="Manage subnets.",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> NetworkingClient:
    return NetworkingClient(make_client(ctx))


@subnet_app.command("list")
def list_subnets(
    ctx: typer.Context,
    network_id: Annotated[
        str | None,
        typer.Option("--network", "-N", help="Filter by parent network ID."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by name substring."),
    ] = None,
) -> None:
    """List subnets.

    Example:

        neviri subnet list
        neviri subnet list --network net-abc
    """
    try:
        emit(ctx, _client(ctx).list_subnets(network_id=network_id, name=name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@subnet_app.command("get")
def get_subnet(
    ctx: typer.Context,
    subnet_id: Annotated[str, typer.Argument(help="Subnet ID.")],
) -> None:
    """Show details of a subnet.

    Example:

        neviri subnet get sub-abc
    """
    try:
        emit(ctx, _client(ctx).get_subnet(subnet_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@subnet_app.command("create")
def create_subnet(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Subnet name.")],
    network_id: Annotated[str, typer.Option("--network", "-N", help="Parent network ID.")],
    cidr: Annotated[str, typer.Option("--cidr", "-c", help="CIDR notation, e.g. 10.0.0.0/24.")],
    ip_version: Annotated[int, typer.Option("--ip-version", help="IP version (4 or 6).")] = 4,
    gateway_ip: Annotated[
        str | None,
        typer.Option("--gateway-ip", help="Gateway IP address."),
    ] = None,
    no_dhcp: Annotated[
        bool, typer.Option("--no-dhcp", help="Disable DHCP on this subnet.")
    ] = False,
    dns: Annotated[
        list[str] | None,
        typer.Option("--dns", help="DNS nameserver IP. Repeatable."),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
) -> None:
    """Create a subnet.

    Example:

        neviri subnet create web-sub \\
            --network net-abc --cidr 10.0.0.0/24 --gateway-ip 10.0.0.1
    """
    body: dict[str, Any] = {
        "name": name,
        "network_id": network_id,
        "cidr": cidr,
        "ip_version": ip_version,
        "enable_dhcp": not no_dhcp,
    }
    if gateway_ip:
        body["gateway_ip"] = gateway_ip
    if dns:
        body["dns_nameservers"] = dns
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).create_subnet(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@subnet_app.command("delete")
def delete_subnet(
    ctx: typer.Context,
    subnet_id: Annotated[str, typer.Argument(help="Subnet ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a subnet.

    Example:

        neviri subnet delete sub-abc --yes
    """
    confirm_or_exit(f"Delete subnet {subnet_id}? This cannot be undone.", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_subnet(subnet_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
