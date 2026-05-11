"""End-to-end tests for `neviri vm` subcommands.

Stack tested: CLI → factory → BaseClient → mocked backend (respx) → output.
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
PREFIX = "/api/v1/compute"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    """Place a token in the active store so make_client succeeds."""
    store_token("default", "test-token")


# ---------- list ----------


@respx.mock
def test_vm_list_renders_table_by_default(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [
                    {"id": "s1", "name": "web-01", "status": "ACTIVE"},
                    {"id": "s2", "name": "web-02", "status": "SHUTOFF"},
                ],
                "message": "ok",
            },
        )
    )
    result = runner.invoke(app, ["--no-color", "vm", "list"])
    assert result.exit_code == 0, result.stdout
    assert "web-01" in result.stdout
    assert "web-02" in result.stdout
    assert "ACTIVE" in result.stdout


@respx.mock
def test_vm_list_json_output(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"id": "s1", "name": "web"}], "message": "ok"},
        )
    )
    result = runner.invoke(app, ["--output", "json", "vm", "list"])
    assert result.exit_code == 0
    assert '"id": "s1"' in result.stdout


@respx.mock
def test_vm_list_passes_filter_flags(logged_in: None, runner: CliRunner) -> None:
    route = respx.get(f"{BACKEND}{PREFIX}/servers").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    result = runner.invoke(app, ["vm", "list", "--status", "ACTIVE", "--name", "web"])
    assert result.exit_code == 0
    qs = route.calls.last.request.url.query.decode()
    assert "status=ACTIVE" in qs
    assert "name=web" in qs


def test_vm_list_without_login_returns_3(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["vm", "list"])
    assert result.exit_code == 3
    assert "Not logged in" in result.stderr


# ---------- get ----------


@respx.mock
def test_vm_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"id": "abc", "name": "web", "status": "ACTIVE"})
    )
    result = runner.invoke(app, ["--output", "json", "vm", "get", "abc"])
    assert result.exit_code == 0
    assert '"abc"' in result.stdout


# ---------- create ----------


@respx.mock
def test_vm_create_posts_required_fields(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers").mock(
        return_value=httpx.Response(201, json={"id": "new", "name": "web"})
    )
    result = runner.invoke(
        app,
        [
            "vm",
            "create",
            "web",
            "--flavor",
            "f1",
            "--image",
            "i1",
            "--network",
            "n1",
        ],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert '"name": "web"' in body or '"name":"web"' in body
    assert "f1" in body
    assert "i1" in body
    assert "n1" in body


@respx.mock
def test_vm_create_with_optional_flags(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers").mock(
        return_value=httpx.Response(201, json={"id": "new"})
    )
    result = runner.invoke(
        app,
        [
            "vm",
            "create",
            "web",
            "-f",
            "f1",
            "-i",
            "i1",
            "-N",
            "n1",
            "--key-name",
            "alice-laptop",
            "--security-group",
            "web",
            "--security-group",
            "ssh",
            "--availability-zone",
            "us-east-1a",
        ],
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "alice-laptop" in body
    assert "us-east-1a" in body
    assert "web" in body and "ssh" in body


# ---------- delete ----------


@respx.mock
def test_vm_delete_with_yes_skips_prompt(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"message": "VM 'abc' deletion initiated"})
    )
    result = runner.invoke(app, ["vm", "delete", "abc", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_vm_delete_aborts_without_confirmation(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["vm", "delete", "abc"], input="n\n")
    assert result.exit_code == 0
    assert "Aborted" in result.stdout
    # Backend should NOT have been called.
    assert route.call_count == 0


@respx.mock
def test_vm_delete_with_force_passes_query_param(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    runner.invoke(app, ["vm", "delete", "abc", "--yes", "--force"])
    assert route.calls.last.request.url.query == b"force=true"


# ---------- power actions ----------


@respx.mock
def test_vm_start(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers/abc/action").mock(
        return_value=httpx.Response(200, json={"message": "started"})
    )
    result = runner.invoke(app, ["vm", "start", "abc"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "start" in body


@respx.mock
def test_vm_stop(logged_in: None, runner: CliRunner) -> None:
    respx.post(f"{BACKEND}{PREFIX}/servers/abc/action").mock(
        return_value=httpx.Response(200, json={"message": "stopped"})
    )
    result = runner.invoke(app, ["vm", "stop", "abc"])
    assert result.exit_code == 0


@respx.mock
def test_vm_reboot_default_is_soft(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers/abc/action").mock(
        return_value=httpx.Response(200, json={"message": "rebooting"})
    )
    runner.invoke(app, ["vm", "reboot", "abc"])
    body = route.calls.last.request.read().decode()
    assert "SOFT" in body


@respx.mock
def test_vm_reboot_hard_passes_HARD(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers/abc/action").mock(
        return_value=httpx.Response(200, json={"message": "rebooting"})
    )
    runner.invoke(app, ["vm", "reboot", "abc", "--hard"])
    body = route.calls.last.request.read().decode()
    assert "HARD" in body


# ---------- resize ----------


@respx.mock
def test_vm_resize_with_yes(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers/abc/resize").mock(
        return_value=httpx.Response(200, json={"message": "resizing"})
    )
    result = runner.invoke(app, ["vm", "resize", "abc", "--flavor", "f-large", "--yes"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "f-large" in body


@respx.mock
def test_vm_resize_aborts_on_no_confirm(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/servers/abc/resize").mock(
        return_value=httpx.Response(200, json={"message": "resizing"})
    )
    result = runner.invoke(app, ["vm", "resize", "abc", "--flavor", "f-large"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


@respx.mock
def test_vm_resize_confirm_and_revert(logged_in: None, runner: CliRunner) -> None:
    respx.post(f"{BACKEND}{PREFIX}/servers/abc/resize/confirm").mock(
        return_value=httpx.Response(200, json={"message": "confirmed"})
    )
    respx.post(f"{BACKEND}{PREFIX}/servers/abc/resize/revert").mock(
        return_value=httpx.Response(200, json={"message": "reverted"})
    )
    assert runner.invoke(app, ["vm", "resize-confirm", "abc"]).exit_code == 0
    assert runner.invoke(app, ["vm", "resize-revert", "abc"]).exit_code == 0


# ---------- console ----------


@respx.mock
def test_vm_console_prints_url(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers/abc/console").mock(
        return_value=httpx.Response(
            200, json={"console_type": "novnc", "url": "https://vnc.example/abc"}
        )
    )
    result = runner.invoke(app, ["vm", "console", "abc"])
    assert result.exit_code == 0
    assert "https://vnc.example/abc" in result.stdout


@respx.mock
def test_vm_console_launch_opens_browser(
    logged_in: None, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers/abc/console").mock(
        return_value=httpx.Response(
            200, json={"console_type": "novnc", "url": "https://vnc.example/abc"}
        )
    )
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    result = runner.invoke(app, ["vm", "console", "abc", "--launch"])
    assert result.exit_code == 0
    assert opened == ["https://vnc.example/abc"]


@respx.mock
def test_vm_console_missing_url_in_response_is_user_error(
    logged_in: None, runner: CliRunner
) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers/abc/console").mock(
        return_value=httpx.Response(200, json={"console_type": "novnc"})  # no url
    )
    result = runner.invoke(app, ["vm", "console", "abc"])
    assert result.exit_code == 2


# ---------- flavors / images ----------


@respx.mock
def test_vm_flavors(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/flavors").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [{"id": "f1", "name": "m1.small", "vcpus": 1}],
                "message": "ok",
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "vm", "flavors"])
    assert result.exit_code == 0
    assert "m1.small" in result.stdout


@respx.mock
def test_vm_images(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/images").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [{"id": "i1", "name": "ubuntu-22.04"}],
                "message": "ok",
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "vm", "images"])
    assert result.exit_code == 0
    assert "ubuntu-22.04" in result.stdout


# ---------- error mapping ----------


@respx.mock
def test_vm_get_404_maps_to_user_error(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Server not found"})
    )
    result = runner.invoke(app, ["vm", "get", "missing"])
    assert result.exit_code == 2
    assert "Server not found" in result.stderr


@respx.mock
def test_vm_list_500_maps_to_server_error(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/servers").mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, ["vm", "list"])
    assert result.exit_code == 5


# Parameterised: every command's `except NeviriCLIError` branch should map
# a backend 500 to exit code 5. This walks all the command paths so we don't
# leave any catch handler untested.
_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    ("GET", f"{BACKEND}{PREFIX}/servers", ["vm", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/servers/abc", ["vm", "get", "abc"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/servers",
        ["vm", "create", "x", "-f", "f", "-i", "i", "-N", "n"],
    ),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/servers/abc",
        ["vm", "delete", "abc", "--yes"],
    ),
    ("POST", f"{BACKEND}{PREFIX}/servers/abc/action", ["vm", "start", "abc"]),
    ("POST", f"{BACKEND}{PREFIX}/servers/abc/action", ["vm", "stop", "abc"]),
    ("POST", f"{BACKEND}{PREFIX}/servers/abc/action", ["vm", "reboot", "abc"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/servers/abc/resize",
        ["vm", "resize", "abc", "--flavor", "f1", "--yes"],
    ),
    ("POST", f"{BACKEND}{PREFIX}/servers/abc/resize/confirm", ["vm", "resize-confirm", "abc"]),
    ("POST", f"{BACKEND}{PREFIX}/servers/abc/resize/revert", ["vm", "resize-revert", "abc"]),
    ("GET", f"{BACKEND}{PREFIX}/servers/abc/console", ["vm", "console", "abc"]),
    ("GET", f"{BACKEND}{PREFIX}/flavors", ["vm", "flavors"]),
    ("GET", f"{BACKEND}{PREFIX}/images", ["vm", "images"]),
]


@pytest.mark.parametrize(("method", "url", "argv"), _ERROR_PATHS)
@respx.mock
def test_vm_command_500_returns_exit_5(
    method: str,
    url: str,
    argv: list[str],
    logged_in: None,
    runner: CliRunner,
) -> None:
    # 500 is not retried by BaseClient (only 502/503/504/429 are), so this
    # is a fast single-shot call.
    getattr(respx, method.lower())(url).mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, argv)
    assert result.exit_code == 5, (argv, result.stdout, result.stderr)
