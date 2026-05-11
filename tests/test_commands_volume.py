"""End-to-end tests for `neviri volume` subcommands."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token

BACKEND = "http://localhost:8000"
PREFIX = "/api/v1/block-storage"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


@respx.mock
def test_volume_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/volumes").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"id": "v1", "name": "data"}], "message": "ok"},
        )
    )
    result = runner.invoke(app, ["--no-color", "volume", "list"])
    assert result.exit_code == 0, result.stdout
    assert "data" in result.stdout


@respx.mock
def test_volume_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/volumes/v1").mock(
        return_value=httpx.Response(200, json={"id": "v1", "size": 100})
    )
    result = runner.invoke(app, ["--output", "json", "volume", "get", "v1"])
    assert result.exit_code == 0
    assert '"v1"' in result.stdout


@respx.mock
def test_volume_create_with_required_fields(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/volumes").mock(
        return_value=httpx.Response(201, json={"id": "v1"})
    )
    result = runner.invoke(app, ["volume", "create", "data", "--size", "100"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert '"name": "data"' in body or '"name":"data"' in body
    assert "100" in body


@respx.mock
def test_volume_create_with_optional_fields(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/volumes").mock(
        return_value=httpx.Response(201, json={"id": "v1"})
    )
    result = runner.invoke(
        app,
        [
            "volume",
            "create",
            "restore",
            "-S",
            "50",
            "--from-snapshot",
            "snap-xyz",
            "-d",
            "from a snapshot",
            "-t",
            "ssd",
            "-z",
            "us-east-1a",
        ],
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "snap-xyz" in body
    assert "ssd" in body
    assert "us-east-1a" in body


@respx.mock
def test_volume_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/volumes/v1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["volume", "delete", "v1", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_volume_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/volumes/v1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["volume", "delete", "v1"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


@respx.mock
def test_volume_attach_with_device(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/volumes/v1/attach").mock(
        return_value=httpx.Response(200, json={"message": "attached"})
    )
    result = runner.invoke(
        app, ["volume", "attach", "v1", "--server", "srv-1", "--device", "/dev/vdb"]
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "srv-1" in body
    assert "/dev/vdb" in body


@respx.mock
def test_volume_detach(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/volumes/v1/detach").mock(
        return_value=httpx.Response(200, json={"message": "detached"})
    )
    result = runner.invoke(app, ["volume", "detach", "v1", "--server", "srv-1"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "srv-1" in body


@respx.mock
def test_volume_snapshot_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/snapshots").mock(
        return_value=httpx.Response(201, json={"id": "s1"})
    )
    result = runner.invoke(app, ["volume", "snapshot", "v1", "--name", "daily", "-d", "nightly"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "v1" in body
    assert "daily" in body


@respx.mock
def test_volume_snapshots_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/snapshots").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "s1"}], "message": "ok"}
        )
    )
    result = runner.invoke(app, ["--output", "json", "volume", "snapshots"])
    assert result.exit_code == 0
    assert '"s1"' in result.stdout


@respx.mock
def test_volume_snapshot_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/snapshots/s1").mock(
        return_value=httpx.Response(200, json={"id": "s1"})
    )
    result = runner.invoke(app, ["--output", "json", "volume", "snapshot-get", "s1"])
    assert result.exit_code == 0


@respx.mock
def test_volume_snapshot_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/snapshots/s1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["volume", "snapshot-delete", "s1", "--yes"])
    assert result.exit_code == 0


# ---------- error mapping ----------


_VOL_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    ("GET", f"{BACKEND}{PREFIX}/volumes", ["volume", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/volumes/v1", ["volume", "get", "v1"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/volumes",
        ["volume", "create", "data", "--size", "100"],
    ),
    ("DELETE", f"{BACKEND}{PREFIX}/volumes/v1", ["volume", "delete", "v1", "--yes"]),
    (
        "POST",
        f"{BACKEND}{PREFIX}/volumes/v1/attach",
        ["volume", "attach", "v1", "--server", "s1"],
    ),
    (
        "POST",
        f"{BACKEND}{PREFIX}/volumes/v1/detach",
        ["volume", "detach", "v1", "--server", "s1"],
    ),
    (
        "POST",
        f"{BACKEND}{PREFIX}/snapshots",
        ["volume", "snapshot", "v1", "--name", "x"],
    ),
    ("GET", f"{BACKEND}{PREFIX}/snapshots", ["volume", "snapshots"]),
    ("GET", f"{BACKEND}{PREFIX}/snapshots/s1", ["volume", "snapshot-get", "s1"]),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/snapshots/s1",
        ["volume", "snapshot-delete", "s1", "--yes"],
    ),
]


@pytest.mark.parametrize(("method", "url", "argv"), _VOL_ERROR_PATHS)
@respx.mock
def test_volume_command_500_returns_5(
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
