"""End-to-end tests for `neviri lb` commands.

Includes Story 10's E2E workflow: LB → pool → listener → member → HM.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token

BACKEND = "http://localhost:8000"
PREFIX = "/api/v1/load-balancers"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


# ---------- load balancer ----------


@respx.mock
def test_lb_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "lb-1"}], "message": "ok"}
        )
    )
    result = runner.invoke(app, ["--output", "json", "lb", "list"])
    assert result.exit_code == 0
    assert "lb-1" in result.stdout


@respx.mock
def test_lb_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}").mock(
        return_value=httpx.Response(201, json={"id": "lb-1"})
    )
    result = runner.invoke(
        app,
        ["lb", "create", "my-lb", "--vip-subnet", "sub-1", "--vip-address", "10.0.0.10"],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "my-lb" in body
    assert "sub-1" in body
    assert "10.0.0.10" in body


@respx.mock
def test_lb_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/lb-1").mock(return_value=httpx.Response(200, json={"id": "lb-1"}))
    result = runner.invoke(app, ["--output", "json", "lb", "get", "lb-1"])
    assert result.exit_code == 0


@respx.mock
def test_lb_update(logged_in: None, runner: CliRunner) -> None:
    route = respx.put(f"{BACKEND}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"id": "lb-1"})
    )
    result = runner.invoke(app, ["lb", "update", "lb-1", "--name", "renamed", "--admin-down"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "renamed" in body
    assert '"admin_state_up": false' in body or '"admin_state_up":false' in body


@respx.mock
def test_lb_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"message": "deleting"})
    )
    result = runner.invoke(app, ["lb", "delete", "lb-1", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_lb_delete_cascade(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"message": "deleting"})
    )
    runner.invoke(app, ["lb", "delete", "lb-1", "--cascade", "--yes"])
    assert b"cascade=true" in route.calls.last.request.url.query


@respx.mock
def test_lb_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"message": "deleting"})
    )
    result = runner.invoke(app, ["lb", "delete", "lb-1"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


# ---------- listener ----------


@respx.mock
def test_listener_create_upcases_protocol(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/listeners").mock(
        return_value=httpx.Response(201, json={"id": "ls-1"})
    )
    result = runner.invoke(
        app,
        ["lb", "listener", "create", "lb-1", "http-80", "-p", "http", "-P", "80"],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert '"protocol": "HTTP"' in body or '"protocol":"HTTP"' in body


@respx.mock
def test_listener_list_and_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/lb-1/listeners").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "ls-1"}], "message": "ok"}
        )
    )
    respx.get(f"{BACKEND}{PREFIX}/lb-1/listeners/ls-1").mock(
        return_value=httpx.Response(200, json={"id": "ls-1"})
    )
    assert runner.invoke(app, ["lb", "listener", "list", "lb-1"]).exit_code == 0
    assert runner.invoke(app, ["lb", "listener", "get", "lb-1", "ls-1"]).exit_code == 0


@respx.mock
def test_listener_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/lb-1/listeners/ls-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["lb", "listener", "delete", "lb-1", "ls-1", "--yes"])
    assert result.exit_code == 0


# ---------- pool + members ----------


@respx.mock
def test_pool_create_upcases_protocol_and_algorithm(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools").mock(
        return_value=httpx.Response(201, json={"id": "p-1"})
    )
    result = runner.invoke(
        app,
        [
            "lb",
            "pool",
            "create",
            "lb-1",
            "web",
            "-p",
            "http",
            "-a",
            "least_connections",
        ],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "HTTP" in body
    assert "LEAST_CONNECTIONS" in body


@respx.mock
def test_pool_list_get_delete(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/lb-1/pools").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "p-1"}], "message": "ok"}
        )
    )
    respx.get(f"{BACKEND}{PREFIX}/lb-1/pools/p-1").mock(
        return_value=httpx.Response(200, json={"id": "p-1"})
    )
    respx.delete(f"{BACKEND}{PREFIX}/lb-1/pools/p-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert runner.invoke(app, ["lb", "pool", "list", "lb-1"]).exit_code == 0
    assert runner.invoke(app, ["lb", "pool", "get", "lb-1", "p-1"]).exit_code == 0
    assert runner.invoke(app, ["lb", "pool", "delete", "lb-1", "p-1", "--yes"]).exit_code == 0


@respx.mock
def test_pool_member_add(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members").mock(
        return_value=httpx.Response(201, json={"id": "m-1"})
    )
    result = runner.invoke(
        app,
        [
            "lb",
            "pool",
            "member-add",
            "lb-1",
            "p-1",
            "-a",
            "10.0.0.5",
            "-P",
            "80",
            "-w",
            "5",
        ],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "10.0.0.5" in body
    assert '"weight": 5' in body or '"weight":5' in body


@respx.mock
def test_pool_member_list_and_remove(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "m-1"}], "message": "ok"}
        )
    )
    respx.delete(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members/m-1").mock(
        return_value=httpx.Response(200, json={"message": "removed"})
    )
    assert runner.invoke(app, ["lb", "pool", "member-list", "lb-1", "p-1"]).exit_code == 0
    assert (
        runner.invoke(app, ["lb", "pool", "member-remove", "lb-1", "p-1", "m-1", "--yes"]).exit_code
        == 0
    )


# ---------- health monitor ----------


@respx.mock
def test_health_monitor_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor").mock(
        return_value=httpx.Response(201, json={"id": "hm-1"})
    )
    result = runner.invoke(
        app,
        [
            "lb",
            "health-monitor",
            "create",
            "lb-1",
            "p-1",
            "-t",
            "http",
            "--delay",
            "5",
            "--timeout",
            "2",
            "--retries",
            "3",
            "--path",
            "/healthz",
            "--expected",
            "200-299",
        ],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "HTTP" in body  # upcased
    assert "/healthz" in body
    assert "200-299" in body


@respx.mock
def test_health_monitor_get_and_delete(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor/hm-1").mock(
        return_value=httpx.Response(200, json={"id": "hm-1"})
    )
    respx.delete(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor/hm-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert runner.invoke(app, ["lb", "health-monitor", "get", "lb-1", "p-1", "hm-1"]).exit_code == 0
    assert (
        runner.invoke(
            app, ["lb", "health-monitor", "delete", "lb-1", "p-1", "hm-1", "--yes"]
        ).exit_code
        == 0
    )


# ---------- E2E workflow (Story 10.3) ----------


@respx.mock
def test_lb_full_workflow(logged_in: None, runner: CliRunner) -> None:
    """Provision an LB end-to-end: LB → pool → listener → member → HM.

    The "health check passes" line in Story 10's AC requires a real backend +
    routable backend members; not testable at the CLI layer. We verify the
    CLI issues the right calls with the right bodies in the right order.
    """
    lb_post = respx.post(f"{BACKEND}{PREFIX}").mock(
        return_value=httpx.Response(201, json={"id": "lb-1", "vip_address": "10.0.0.10"})
    )
    pool_post = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools").mock(
        return_value=httpx.Response(201, json={"id": "p-1"})
    )
    listener_post = respx.post(f"{BACKEND}{PREFIX}/lb-1/listeners").mock(
        return_value=httpx.Response(201, json={"id": "ls-1"})
    )
    member1_post = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members").mock(
        return_value=httpx.Response(201, json={"id": "m-1"})
    )
    hm_post = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor").mock(
        return_value=httpx.Response(201, json={"id": "hm-1"})
    )

    # 1. Create LB
    r = runner.invoke(app, ["lb", "create", "demo-lb", "--vip-subnet", "sub-1"])
    assert r.exit_code == 0, r.stdout
    assert "demo-lb" in lb_post.calls.last.request.read().decode()

    # 2. Create pool
    r = runner.invoke(app, ["lb", "pool", "create", "lb-1", "web-pool", "-p", "HTTP"])
    assert r.exit_code == 0, r.stdout
    assert "web-pool" in pool_post.calls.last.request.read().decode()

    # 3. Create listener that defaults to the pool
    r = runner.invoke(
        app,
        [
            "lb",
            "listener",
            "create",
            "lb-1",
            "http-80",
            "-p",
            "HTTP",
            "-P",
            "80",
            "--default-pool",
            "p-1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    listener_body = listener_post.calls.last.request.read().decode()
    assert "p-1" in listener_body
    assert "80" in listener_body

    # 4. Add a member to the pool
    r = runner.invoke(
        app,
        [
            "lb",
            "pool",
            "member-add",
            "lb-1",
            "p-1",
            "-a",
            "10.0.0.5",
            "-P",
            "80",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "10.0.0.5" in member1_post.calls.last.request.read().decode()

    # 5. Attach a health monitor
    r = runner.invoke(
        app,
        [
            "lb",
            "health-monitor",
            "create",
            "lb-1",
            "p-1",
            "-t",
            "HTTP",
            "--delay",
            "5",
            "--timeout",
            "2",
            "--retries",
            "3",
        ],
    )
    assert r.exit_code == 0, r.stdout
    hm_body = hm_post.calls.last.request.read().decode()
    assert "HTTP" in hm_body

    # All 5 endpoints hit exactly once.
    assert lb_post.call_count == 1
    assert pool_post.call_count == 1
    assert listener_post.call_count == 1
    assert member1_post.call_count == 1
    assert hm_post.call_count == 1


# ---------- error mapping ----------


_LB_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    # LB (5)
    ("GET", f"{BACKEND}{PREFIX}", ["lb", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/lb-1", ["lb", "get", "lb-1"]),
    ("POST", f"{BACKEND}{PREFIX}", ["lb", "create", "x", "--vip-subnet", "s"]),
    ("PUT", f"{BACKEND}{PREFIX}/lb-1", ["lb", "update", "lb-1", "--name", "renamed"]),
    ("DELETE", f"{BACKEND}{PREFIX}/lb-1", ["lb", "delete", "lb-1", "--yes"]),
    # Listener (4)
    ("GET", f"{BACKEND}{PREFIX}/lb-1/listeners", ["lb", "listener", "list", "lb-1"]),
    (
        "GET",
        f"{BACKEND}{PREFIX}/lb-1/listeners/ls-1",
        ["lb", "listener", "get", "lb-1", "ls-1"],
    ),
    (
        "POST",
        f"{BACKEND}{PREFIX}/lb-1/listeners",
        ["lb", "listener", "create", "lb-1", "n", "-p", "HTTP", "-P", "80"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/lb-1/listeners/ls-1",
        ["lb", "listener", "delete", "lb-1", "ls-1", "--yes"],
    ),
    # Pool (4) + members (3)
    ("GET", f"{BACKEND}{PREFIX}/lb-1/pools", ["lb", "pool", "list", "lb-1"]),
    ("GET", f"{BACKEND}{PREFIX}/lb-1/pools/p-1", ["lb", "pool", "get", "lb-1", "p-1"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/lb-1/pools",
        ["lb", "pool", "create", "lb-1", "p", "-p", "HTTP"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1",
        ["lb", "pool", "delete", "lb-1", "p-1", "--yes"],
    ),
    (
        "GET",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members",
        ["lb", "pool", "member-list", "lb-1", "p-1"],
    ),
    (
        "POST",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members",
        ["lb", "pool", "member-add", "lb-1", "p-1", "-a", "10.0.0.5", "-P", "80"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members/m-1",
        ["lb", "pool", "member-remove", "lb-1", "p-1", "m-1", "--yes"],
    ),
    # Health monitor (3)
    (
        "POST",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor",
        [
            "lb",
            "health-monitor",
            "create",
            "lb-1",
            "p-1",
            "-t",
            "HTTP",
            "--delay",
            "5",
            "--timeout",
            "2",
            "--retries",
            "3",
        ],
    ),
    (
        "GET",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor/hm-1",
        ["lb", "health-monitor", "get", "lb-1", "p-1", "hm-1"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor/hm-1",
        ["lb", "health-monitor", "delete", "lb-1", "p-1", "hm-1", "--yes"],
    ),
]


# ---------- optional-field branch coverage ----------


@respx.mock
def test_lb_create_with_description(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}").mock(
        return_value=httpx.Response(201, json={"id": "lb-1"})
    )
    runner.invoke(app, ["lb", "create", "x", "--vip-subnet", "s", "--description", "prod web"])
    body = route.calls.last.request.read().decode()
    assert "prod web" in body


@respx.mock
def test_lb_update_with_description(logged_in: None, runner: CliRunner) -> None:
    route = respx.put(f"{BACKEND}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"id": "lb-1"})
    )
    runner.invoke(app, ["lb", "update", "lb-1", "--description", "new desc"])
    body = route.calls.last.request.read().decode()
    assert "new desc" in body


@respx.mock
def test_listener_create_with_description(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/listeners").mock(
        return_value=httpx.Response(201, json={"id": "ls-1"})
    )
    runner.invoke(
        app,
        ["lb", "listener", "create", "lb-1", "n", "-p", "HTTP", "-P", "80", "-d", "ssl term"],
    )
    body = route.calls.last.request.read().decode()
    assert "ssl term" in body


@respx.mock
def test_pool_create_with_listener_and_description(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools").mock(
        return_value=httpx.Response(201, json={"id": "p-1"})
    )
    runner.invoke(
        app,
        [
            "lb",
            "pool",
            "create",
            "lb-1",
            "p",
            "-p",
            "HTTP",
            "--listener",
            "ls-1",
            "-d",
            "backend pool",
        ],
    )
    body = route.calls.last.request.read().decode()
    assert "ls-1" in body
    assert "backend pool" in body


@respx.mock
def test_member_add_with_name_and_subnet(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/members").mock(
        return_value=httpx.Response(201, json={"id": "m-1"})
    )
    runner.invoke(
        app,
        [
            "lb",
            "pool",
            "member-add",
            "lb-1",
            "p-1",
            "-a",
            "10.0.0.5",
            "-P",
            "80",
            "-n",
            "web-01",
            "--subnet",
            "sub-1",
        ],
    )
    body = route.calls.last.request.read().decode()
    assert "web-01" in body
    assert "sub-1" in body


@respx.mock
def test_health_monitor_create_with_name(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/lb-1/pools/p-1/healthmonitor").mock(
        return_value=httpx.Response(201, json={"id": "hm-1"})
    )
    runner.invoke(
        app,
        [
            "lb",
            "health-monitor",
            "create",
            "lb-1",
            "p-1",
            "-t",
            "HTTP",
            "--delay",
            "5",
            "--timeout",
            "2",
            "--retries",
            "3",
            "-n",
            "primary-hm",
        ],
    )
    body = route.calls.last.request.read().decode()
    assert "primary-hm" in body


@pytest.mark.parametrize(("method", "url", "argv"), _LB_ERROR_PATHS)
@respx.mock
def test_lb_command_500_returns_5(
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
