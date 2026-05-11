"""`neviri network` subcommands. Wraps `/api/v1/network/networks/*`."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from neviri_cli.client.factory import make_client
from neviri_cli.client.networking import NetworkingClient
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error

network_app = typer.Typer(
    name="network",
    help="Manage virtual networks.",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> NetworkingClient:
    return NetworkingClient(make_client(ctx))


@network_app.command("list")
def list_networks(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by name substring."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status (e.g. ACTIVE)."),
    ] = None,
) -> None:
    """List virtual networks.

    Example:

        neviri network list
    """
    try:
        emit(ctx, _client(ctx).list_networks(name=name, status=status))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@network_app.command("get")
def get_network(
    ctx: typer.Context,
    network_id: Annotated[str, typer.Argument(help="Network ID.")],
) -> None:
    """Show details of a network.

    Example:

        neviri network get net-abc
    """
    try:
        emit(ctx, _client(ctx).get_network(network_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@network_app.command("create")
def create_network(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Network name.")],
    shared: Annotated[bool, typer.Option("--shared", help="Share across projects.")] = False,
    external: Annotated[
        bool, typer.Option("--external", help="Mark as an external network.")
    ] = False,
    mtu: Annotated[int | None, typer.Option("--mtu", help="Maximum transmission unit.")] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
) -> None:
    """Create a virtual network.

    Example:

        neviri network create my-net
        neviri network create public-net --external
    """
    body: dict[str, Any] = {"name": name, "shared": shared, "external": external}
    if mtu is not None:
        body["mtu"] = mtu
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).create_network(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@network_app.command("delete")
def delete_network(
    ctx: typer.Context,
    network_id: Annotated[str, typer.Argument(help="Network ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a virtual network.

    Example:

        neviri network delete net-abc --yes
    """
    confirm_or_exit(f"Delete network {network_id}? This cannot be undone.", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_network(network_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
