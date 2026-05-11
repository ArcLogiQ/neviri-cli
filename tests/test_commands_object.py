"""End-to-end tests for `neviri object` (bucket + object subcommands)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token

BACKEND = "http://localhost:8000"
PREFIX = "/api/v1/object-storage"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


# ---------- bucket ops ----------


@respx.mock
def test_bucket_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/containers").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [{"name": "b1", "count": 1, "bytes": 100}],
                "message": "ok",
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "object", "bucket", "list"])
    assert result.exit_code == 0
    assert "b1" in result.stdout


@respx.mock
def test_bucket_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{PREFIX}/containers").mock(
        return_value=httpx.Response(201, json={"name": "b1"})
    )
    result = runner.invoke(
        app, ["object", "bucket", "create", "b1", "-m", "env=prod", "-m", "owner=sre"]
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "env" in body and "prod" in body
    assert "owner" in body and "sre" in body


def test_bucket_create_bad_metadata(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "test-token")
    result = runner.invoke(app, ["object", "bucket", "create", "b1", "-m", "novalue"])
    assert result.exit_code == 2


@respx.mock
def test_bucket_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/containers/b1").mock(
        return_value=httpx.Response(200, json={"name": "b1", "count": 5})
    )
    result = runner.invoke(app, ["--output", "json", "object", "bucket", "get", "b1"])
    assert result.exit_code == 0


@respx.mock
def test_bucket_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/containers/b1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["object", "bucket", "delete", "b1", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_bucket_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{PREFIX}/containers/b1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["object", "bucket", "delete", "b1"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


# ---------- object ops ----------


@respx.mock
def test_object_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PREFIX}/containers/b1/objects").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"name": "a.txt"}], "message": "ok"},
        )
    )
    result = runner.invoke(app, ["--output", "json", "object", "list", "b1"])
    assert result.exit_code == 0
    assert "a.txt" in result.stdout


@respx.mock
def test_object_list_with_prefix(logged_in: None, runner: CliRunner) -> None:
    route = respx.get(f"{BACKEND}{PREFIX}/containers/b1/objects").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    result = runner.invoke(app, ["object", "list", "b1", "--prefix", "logs/"])
    assert result.exit_code == 0
    assert b"prefix=logs" in route.calls.last.request.url.query


@respx.mock
def test_object_put_uploads_file_no_progress(
    logged_in: None, runner: CliRunner, tmp_path: Path
) -> None:
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello-world")

    route = respx.put(f"{BACKEND}{PREFIX}/containers/b1/objects/data.bin").mock(
        return_value=httpx.Response(200, json={"etag": "abc", "name": "data.bin"})
    )
    result = runner.invoke(
        app,
        [
            "object",
            "put",
            "b1",
            "data.bin",
            "--file",
            str(f),
            "--no-progress",
        ],
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read()
    assert b"hello-world" in body


@respx.mock
def test_object_put_with_custom_content_type(
    logged_in: None, runner: CliRunner, tmp_path: Path
) -> None:
    f = tmp_path / "x.json"
    f.write_text('{"a": 1}')

    route = respx.put(f"{BACKEND}{PREFIX}/containers/b1/objects/x.json").mock(
        return_value=httpx.Response(200, json={"etag": "j"})
    )
    result = runner.invoke(
        app,
        [
            "object",
            "put",
            "b1",
            "x.json",
            "--file",
            str(f),
            "--content-type",
            "application/json",
            "--no-progress",
        ],
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read()
    assert b"application/json" in body


def test_object_put_missing_file(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "test-token")
    result = runner.invoke(
        app,
        [
            "object",
            "put",
            "b1",
            "x",
            "--file",
            "/this/path/definitely/does/not/exist",
            "--no-progress",
        ],
    )
    # Typer's `exists=True` validator rejects before any HTTP call
    assert result.exit_code != 0


@respx.mock
def test_object_get_writes_file(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    respx.get(f"{BACKEND}{PREFIX}/containers/b1/objects/file.bin").mock(
        return_value=httpx.Response(200, content=b"binary-payload")
    )
    dest = tmp_path / "out.bin"
    result = runner.invoke(
        app,
        [
            "object",
            "get",
            "b1",
            "file.bin",
            "-o",
            str(dest),
            "--no-progress",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert dest.read_bytes() == b"binary-payload"


@respx.mock
def test_object_get_404_returns_2(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    respx.get(f"{BACKEND}{PREFIX}/containers/b1/objects/missing").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    result = runner.invoke(
        app,
        [
            "object",
            "get",
            "b1",
            "missing",
            "-o",
            str(tmp_path / "out.bin"),
            "--no-progress",
        ],
    )
    assert result.exit_code == 2


@respx.mock
def test_object_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{PREFIX}/containers/b1/objects/x.txt").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["object", "delete", "b1", "x.txt", "--yes"])
    assert result.exit_code == 0


# ---------- error mapping ----------


_OBJ_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    ("GET", f"{BACKEND}{PREFIX}/containers", ["object", "bucket", "list"]),
    ("GET", f"{BACKEND}{PREFIX}/containers/b1", ["object", "bucket", "get", "b1"]),
    ("POST", f"{BACKEND}{PREFIX}/containers", ["object", "bucket", "create", "b1"]),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/containers/b1",
        ["object", "bucket", "delete", "b1", "--yes"],
    ),
    ("GET", f"{BACKEND}{PREFIX}/containers/b1/objects", ["object", "list", "b1"]),
    (
        "DELETE",
        f"{BACKEND}{PREFIX}/containers/b1/objects/x.txt",
        ["object", "delete", "b1", "x.txt", "--yes"],
    ),
]


@pytest.mark.parametrize(("method", "url", "argv"), _OBJ_ERROR_PATHS)
@respx.mock
def test_object_command_500_returns_5(
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
