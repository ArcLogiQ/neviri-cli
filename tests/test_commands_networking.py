"""End-to-end tests for `neviri network`, `subnet`, and `floating-ip`."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token

BACKEND = "http://localhost:8000"
PREFIX = "/api/v1/network"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


# ---------- network ----------


@respx.mock
def test_network_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/networks").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "n1", "name": "my-net"}], "message": "ok"}
        )
    )
    result = runner.invoke(app, ["--output", "json", "network", "list"])
    assert result.exit_code == 0
    assert "my-net" in result.stdout


@respx.mock
def test_network_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/networks").mock(
        return_value=httpx.Response(201, json={"id": "n1"})
    )
    result = runner.invoke(app, ["network", "create", "my-net", "--shared", "--mtu", "1500"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "my-net" in body
    assert '"shared": true' in body or '"shared":true' in body
    assert "1500" in body


@respx.mock
def test_network_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/networks/n1").mock(
        return_value=httpx.Response(200, json={"id": "n1"})
    )
    result = runner.invoke(app, ["--output", "json", "network", "get", "n1"])
    assert result.exit_code == 0


@respx.mock
def test_network_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/networks/n1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["network", "delete", "n1", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_network_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/networks/n1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["network", "delete", "n1"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


# ---------- subnet ----------


@respx.mock
def test_subnet_list_with_network_filter(logged_in: None, runner: CliRunner) -> None:
    route = respx.get(f"{BACKEND}{PREFIX}/subnets").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    result = runner.invoke(app, ["subnet", "list", "--network", "n1"])
    assert result.exit_code == 0
    assert b"network_id=n1" in route.calls.last.request.url.query


@respx.mock
def test_subnet_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/subnets").mock(
        return_value=httpx.Response(201, json={"id": "s1"})
    )
    result = runner.invoke(
        app,
        [
            "subnet",
            "create",
            "web-sub",
            "--network",
            "n1",
            "--cidr",
            "10.0.0.0/24",
            "--gateway-ip",
            "10.0.0.1",
            "--dns",
            "8.8.8.8",
            "--dns",
            "1.1.1.1",
        ],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "10.0.0.0/24" in body
    assert "10.0.0.1" in body
    assert "8.8.8.8" in body and "1.1.1.1" in body


@respx.mock
def test_subnet_create_no_dhcp(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/subnets").mock(
        return_value=httpx.Response(201, json={"id": "s1"})
    )
    runner.invoke(
        app,
        ["subnet", "create", "no-dhcp", "--network", "n1", "--cidr", "10.0.0.0/24", "--no-dhcp"],
    )
    body = route.calls.last.request.read().decode()
    assert '"enable_dhcp": false' in body or '"enable_dhcp":false' in body


@respx.mock
def test_subnet_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/subnets/s1").mock(
        return_value=httpx.Response(200, json={"id": "s1"})
    )
    result = runner.invoke(app, ["--output", "json", "subnet", "get", "s1"])
    assert result.exit_code == 0


@respx.mock
def test_subnet_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/subnets/s1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["subnet", "delete", "s1", "--yes"])
    assert result.exit_code == 0


# ---------- floating-ip ----------


@respx.mock
def test_floating_ip_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/floating-ips").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [{"id": "fip", "floating_ip_address": "1.2.3.4"}],
                "message": "ok",
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "floating-ip", "list"])
    assert result.exit_code == 0
    assert "1.2.3.4" in result.stdout


@respx.mock
def test_floating_ip_allocate(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/floating-ips").mock(
        return_value=httpx.Response(201, json={"id": "fip"})
    )
    result = runner.invoke(
        app, ["floating-ip", "allocate", "--floating-network", "ext-net", "-d", "for web"]
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "ext-net" in body
    assert "for web" in body


@respx.mock
def test_floating_ip_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/floating-ips/fip").mock(
        return_value=httpx.Response(200, json={"id": "fip"})
    )
    result = runner.invoke(app, ["--output", "json", "floating-ip", "get", "fip"])
    assert result.exit_code == 0


@respx.mock
def test_floating_ip_release_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/floating-ips/fip").mock(
        return_value=httpx.Response(200, json={"message": "released"})
    )
    result = runner.invoke(app, ["floating-ip", "release", "fip", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_floating_ip_associate(logged_in: None, runner: CliRunner) -> None:
    route = respx.put(f"{BACKEND}{PREFIX}/floating-ips/fip/associate").mock(
        return_value=httpx.Response(200, json={"id": "fip", "port_id": "p1"})
    )
    result = runner.invoke(app, ["floating-ip", "associate", "fip", "--port", "p1"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "p1" in body


@respx.mock
def test_floating_ip_disassociate(logged_in: None, runner: CliRunner) -> None:
    respx.put(f"{BACKEND}{PREFIX}/floating-ips/fip/disassociate").mock(
        return_value=httpx.Response(200, json={"id": "fip", "port_id": None})
    )
    result = runner.invoke(app, ["floating-ip", "disassociate", "fip"])
    assert result.exit_code == 0


# ---------- error mapping (parametrized across all 3 groups) ----------


_NET_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    # network
    ("GET", f"{BACKEND}{PREFIX}/networks", ["network", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/networks/n1", ["network", "get", "n1"]),
    ("POST", f"{BACKEND}{PREFIX}/networks", ["network", "create", "my"]),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/networks/n1",
        ["network", "delete", "n1", "--yes"],
    ),
    # subnet
    ("GET", f"{BACKEND}{PREFIX}/subnets", ["subnet", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/subnets/s1", ["subnet", "get", "s1"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/subnets",
        ["subnet", "create", "x", "--network", "n", "--cidr", "10.0.0.0/24"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/subnets/s1",
        ["subnet", "delete", "s1", "--yes"],
    ),
    # floating-ip
    ("GET", f"{BACKEND}{PREFIX}/floating-ips", ["floating-ip", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/floating-ips/fip", ["floating-ip", "get", "fip"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/floating-ips",
        ["floating-ip", "allocate", "--floating-network", "ext"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/floating-ips/fip",
        ["floating-ip", "release", "fip", "--yes"],
    ),
    (
        "PUT",
        f"{BACKEND}{PREFIX}/floating-ips/fip/associate",
        ["floating-ip", "associate", "fip", "--port", "p1"],
    ),
    (
        "PUT",
        f"{BACKEND}{PREFIX}/floating-ips/fip/disassociate",
        ["floating-ip", "disassociate", "fip"],
    ),
]


@pytest.mark.parametrize(("method", "url", "argv"), _NET_ERROR_PATHS)
@respx.mock
def test_networking_command_500_returns_5(
    method: str,
    url: str,
    argv: list[str],
    logged_in: None,
    runner: CliRunner,
) -> None:
    getattr(respx, method.lower())(url).mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, argv)
    assert result.exit_code == 5, (argv, result.stdout, result.stderr)
