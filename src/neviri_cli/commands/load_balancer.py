"""`neviri lb` subcommands. Wraps `/api/v1/load-balancers/*`.

Layout (matches proposal section 4.5):

    neviri lb {list,get,create,delete,update}
    neviri lb listener       {list,get,create,delete}
    neviri lb pool           {list,get,create,delete,
                              member-list,member-add,member-remove}
    neviri lb health-monitor {get,create,delete}

Members live under pool because the backend URL is
``/load-balancers/{lb_id}/pools/{pool_id}/members/...``. Health monitors are
one-per-pool on the backend (no list endpoint), so the CLI omits ``list``.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from neviri_cli.client.factory import make_client
from neviri_cli.client.load_balancer import LoadBalancerClient
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error

lb_app = typer.Typer(
    name="lb",
    help="Manage load balancers, listeners, pools, members, and health monitors.",
    no_args_is_help=True,
)
listener_app = typer.Typer(
    name="listener", help="Manage listeners on a load balancer.", no_args_is_help=True
)
pool_app = typer.Typer(
    name="pool",
    help="Manage backend pools and their members on a load balancer.",
    no_args_is_help=True,
)
hm_app = typer.Typer(
    name="health-monitor",
    help="Manage health monitors on a pool.",
    no_args_is_help=True,
)
lb_app.add_typer(listener_app, name="listener")
lb_app.add_typer(pool_app, name="pool")
lb_app.add_typer(hm_app, name="health-monitor")


def _client(ctx: typer.Context) -> LoadBalancerClient:
    return LoadBalancerClient(make_client(ctx))


# ============================================================
# Load balancer
# ============================================================


@lb_app.command("list")
def list_lbs(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by name substring."),
    ] = None,
) -> None:
    """List load balancers.

    Example:

        neviri lb list
    """
    try:
        emit(ctx, _client(ctx).list_load_balancers(name=name))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@lb_app.command("get")
def get_lb(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
) -> None:
    """Show details of a load balancer."""
    try:
        emit(ctx, _client(ctx).get_load_balancer(lb_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@lb_app.command("create")
def create_lb(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name.")],
    vip_subnet: Annotated[str, typer.Option("--vip-subnet", help="Subnet ID for the VIP.")],
    vip_address: Annotated[
        str | None,
        typer.Option("--vip-address", help="Specific VIP address (otherwise auto-allocated)."),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
) -> None:
    """Create a load balancer.

    Example:

        neviri lb create my-lb --vip-subnet sub-abc
    """
    body: dict[str, Any] = {"name": name, "vip_subnet_id": vip_subnet}
    if vip_address:
        body["vip_address"] = vip_address
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).create_load_balancer(body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@lb_app.command("update")
def update_lb(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    name: Annotated[str | None, typer.Option("--name", help="New name.")] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="New description.")
    ] = None,
    admin_up: Annotated[
        bool | None,
        typer.Option(
            "--admin-up/--admin-down",
            help="Bring the LB administratively up or down.",
        ),
    ] = None,
) -> None:
    """Update load-balancer attributes."""
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if admin_up is not None:
        body["admin_state_up"] = admin_up
    try:
        emit(ctx, _client(ctx).update_load_balancer(lb_id, body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@lb_app.command("delete")
def delete_lb(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    cascade: Annotated[
        bool,
        typer.Option(
            "--cascade",
            help="Delete listeners, pools, members, and health monitors too.",
        ),
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a load balancer."""
    suffix = " and all child resources" if cascade else ""
    confirm_or_exit(f"Delete load balancer {lb_id}{suffix}?", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_load_balancer(lb_id, cascade=cascade))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ============================================================
# Listener
# ============================================================


@listener_app.command("list")
def list_listeners(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
) -> None:
    """List listeners attached to a load balancer."""
    try:
        emit(ctx, _client(ctx).list_listeners(lb_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@listener_app.command("get")
def get_listener(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    listener_id: Annotated[str, typer.Argument(help="Listener ID.")],
) -> None:
    """Show details of a listener."""
    try:
        emit(ctx, _client(ctx).get_listener(lb_id, listener_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@listener_app.command("create")
def create_listener(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    name: Annotated[str, typer.Argument(help="Listener name.")],
    protocol: Annotated[
        str,
        typer.Option("--protocol", "-p", help="HTTP, HTTPS, TCP, UDP, or TERMINATED_HTTPS."),
    ],
    port: Annotated[
        int, typer.Option("--port", "-P", help="Listening port (1-65535).", min=1, max=65535)
    ],
    default_pool: Annotated[
        str | None,
        typer.Option("--default-pool", help="Default backend pool ID."),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
) -> None:
    """Create a listener on a load balancer.

    Example:

        neviri lb listener create lb-1 http-80 -p HTTP -P 80
    """
    body: dict[str, Any] = {
        "name": name,
        "protocol": protocol.upper(),
        "protocol_port": port,
    }
    if default_pool:
        body["default_pool_id"] = default_pool
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).create_listener(lb_id, body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@listener_app.command("delete")
def delete_listener(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    listener_id: Annotated[str, typer.Argument(help="Listener ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a listener."""
    confirm_or_exit(f"Delete listener {listener_id} from {lb_id}?", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_listener(lb_id, listener_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ============================================================
# Pool (and members)
# ============================================================


@pool_app.command("list")
def list_pools(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
) -> None:
    """List backend pools attached to a load balancer."""
    try:
        emit(ctx, _client(ctx).list_pools(lb_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@pool_app.command("get")
def get_pool(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
) -> None:
    """Show details of a pool."""
    try:
        emit(ctx, _client(ctx).get_pool(lb_id, pool_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@pool_app.command("create")
def create_pool(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    name: Annotated[str, typer.Argument(help="Pool name.")],
    protocol: Annotated[
        str,
        typer.Option("--protocol", "-p", help="HTTP, HTTPS, TCP, UDP, or PROXY."),
    ],
    algorithm: Annotated[
        str,
        typer.Option(
            "--algorithm",
            "-a",
            help="ROUND_ROBIN (default), LEAST_CONNECTIONS, SOURCE_IP, SOURCE_IP_PORT.",
        ),
    ] = "ROUND_ROBIN",
    listener: Annotated[
        str | None,
        typer.Option("--listener", help="Listener ID to associate the pool with."),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description.")
    ] = None,
) -> None:
    """Create a backend pool on a load balancer.

    Example:

        neviri lb pool create lb-1 web-pool -p HTTP
    """
    body: dict[str, Any] = {
        "name": name,
        "protocol": protocol.upper(),
        "lb_algorithm": algorithm.upper(),
    }
    if listener:
        body["listener_id"] = listener
    if description:
        body["description"] = description
    try:
        emit(ctx, _client(ctx).create_pool(lb_id, body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@pool_app.command("delete")
def delete_pool(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a pool."""
    confirm_or_exit(f"Delete pool {pool_id} from {lb_id}?", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_pool(lb_id, pool_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@pool_app.command("member-list")
def list_pool_members(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
) -> None:
    """List members in a pool."""
    try:
        emit(ctx, _client(ctx).list_members(lb_id, pool_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@pool_app.command("member-add")
def add_pool_member(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
    address: Annotated[str, typer.Option("--address", "-a", help="Member IP address.")],
    port: Annotated[
        int, typer.Option("--port", "-P", help="Member port (1-65535).", min=1, max=65535)
    ],
    weight: Annotated[
        int, typer.Option("--weight", "-w", help="Routing weight (0-256).", min=0, max=256)
    ] = 1,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Member name.")] = None,
    subnet: Annotated[
        str | None, typer.Option("--subnet", help="Subnet ID for the member.")
    ] = None,
) -> None:
    """Add a member to a pool.

    Example:

        neviri lb pool member-add lb-1 pool-1 -a 10.0.0.5 -P 80
    """
    body: dict[str, Any] = {
        "address": address,
        "protocol_port": port,
        "weight": weight,
    }
    if name:
        body["name"] = name
    if subnet:
        body["subnet_id"] = subnet
    try:
        emit(ctx, _client(ctx).create_member(lb_id, pool_id, body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@pool_app.command("member-remove")
def remove_pool_member(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
    member_id: Annotated[str, typer.Argument(help="Member ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Remove a member from a pool."""
    confirm_or_exit(f"Remove member {member_id} from pool {pool_id}?", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_member(lb_id, pool_id, member_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ============================================================
# Health monitor
# ============================================================


@hm_app.command("create")
def create_health_monitor(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
    hm_type: Annotated[
        str,
        typer.Option("--type", "-t", help="HTTP, HTTPS, PING, TCP, or UDP-CONNECT."),
    ],
    delay: Annotated[int, typer.Option("--delay", help="Seconds between checks.", min=1)],
    timeout: Annotated[int, typer.Option("--timeout", help="Seconds to wait for response.", min=1)],
    retries: Annotated[
        int,
        typer.Option(
            "--retries", help="Number of retries before marking unhealthy (1-10).", min=1, max=10
        ),
    ],
    http_method: Annotated[
        str,
        typer.Option("--method", help="HTTP method for HTTP/HTTPS checks."),
    ] = "GET",
    url_path: Annotated[
        str,
        typer.Option("--path", help="URL path for HTTP/HTTPS checks."),
    ] = "/",
    expected_codes: Annotated[
        str,
        typer.Option("--expected", help="Expected HTTP status codes (e.g. 200 or 200-299)."),
    ] = "200",
    name: Annotated[str | None, typer.Option("--name", "-n", help="Health monitor name.")] = None,
) -> None:
    """Create a health monitor on a pool.

    Example:

        neviri lb health-monitor create lb-1 pool-1 -t HTTP --delay 5 --timeout 2 --retries 3
    """
    body: dict[str, Any] = {
        "type": hm_type.upper(),
        "delay": delay,
        "timeout": timeout,
        "max_retries": retries,
        "http_method": http_method,
        "url_path": url_path,
        "expected_codes": expected_codes,
    }
    if name:
        body["name"] = name
    try:
        emit(ctx, _client(ctx).create_health_monitor(lb_id, pool_id, body))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@hm_app.command("get")
def get_health_monitor(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
    hm_id: Annotated[str, typer.Argument(help="Health monitor ID.")],
) -> None:
    """Show details of a health monitor."""
    try:
        emit(ctx, _client(ctx).get_health_monitor(lb_id, pool_id, hm_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@hm_app.command("delete")
def delete_health_monitor(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID.")],
    pool_id: Annotated[str, typer.Argument(help="Pool ID.")],
    hm_id: Annotated[str, typer.Argument(help="Health monitor ID.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a health monitor."""
    confirm_or_exit(f"Delete health monitor {hm_id} from pool {pool_id}?", yes=yes)
    try:
        emit(ctx, _client(ctx).delete_health_monitor(lb_id, pool_id, hm_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
