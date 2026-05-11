"""End-to-end tests for `neviri db {mysql|pg|mongo}` subcommands.

The three engines share a single command builder so we exercise the shape on
one engine (MySQL) per command and add minimum-coverage smoke tests for PG /
Mongo where the URL or body shape differs.
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


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


# ---------- list / get / status (MySQL) ----------


@respx.mock
def test_mysql_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/mysql/all-mysql").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"id": 1, "name": "db-01"}], "message": "ok"},
        )
    )
    result = runner.invoke(app, ["--output", "json", "db", "mysql", "list"])
    assert result.exit_code == 0, result.stdout
    assert "db-01" in result.stdout


@respx.mock
def test_mysql_get_filters_from_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/mysql/all-mysql").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
                "message": "ok",
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "db", "mysql", "get", "2"])
    assert result.exit_code == 0
    assert '"b"' in result.stdout


@respx.mock
def test_mysql_get_404_when_missing(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/mysql/all-mysql").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    result = runner.invoke(app, ["db", "mysql", "get", "99"])
    assert result.exit_code == 2


@respx.mock
def test_mysql_status(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/mysql/status-mysql/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "status": "ACTIVE"})
    )
    result = runner.invoke(app, ["--output", "json", "db", "mysql", "status", "1"])
    assert result.exit_code == 0


@respx.mock
def test_mysql_flavors(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/mysql/flavors").mock(
        return_value=httpx.Response(
            200,
            json={"flavors": [{"name": "SMALL", "cpu": 1, "ram": 2, "storage": "20Gi"}]},
        )
    )
    result = runner.invoke(app, ["--output", "json", "db", "mysql", "flavors"])
    assert result.exit_code == 0
    assert "SMALL" in result.stdout


# ---------- create (with --password-stdin) ----------


@respx.mock
def test_mysql_create_with_password_stdin(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}/api/v1/mysql/create-mysql").mock(
        return_value=httpx.Response(201, json={"id": 1, "name": "db-01"})
    )
    result = runner.invoke(
        app,
        [
            "db",
            "mysql",
            "create",
            "db-01",
            "--flavor",
            "SMALL",
            "--user",
            "admin",
            "--db-name",
            "app",
            "--password-stdin",
        ],
        input="hunter2\n",
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "db-01" in body
    assert "admin" in body
    assert "hunter2" in body
    # Password should be on the right schema field
    assert "mysql_pass" in body


@respx.mock
def test_mysql_create_empty_stdin_password_rejected(logged_in: None, runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        ["db", "mysql", "create", "x", "--user", "u", "--password-stdin"],
        input="\n",
    )
    assert result.exit_code == 2


# ---------- delete / scale (confirmation) ----------


@respx.mock
def test_mysql_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}/api/v1/mysql/delete-mysql/1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["db", "mysql", "delete", "1", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_mysql_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}/api/v1/mysql/delete-mysql/1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["db", "mysql", "delete", "1"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


@respx.mock
def test_mysql_scale_with_yes(logged_in: None, runner: CliRunner) -> None:
    route = respx.put(f"{BACKEND}/api/v1/mysql/scale-mysql/1").mock(
        return_value=httpx.Response(200, json={"message": "scaling"})
    )
    result = runner.invoke(
        app, ["db", "mysql", "scale", "1", "--flavor", "BIG", "--storage", "100", "--yes"]
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "BIG" in body
    assert "100" in body


# ---------- backup / restore ----------


@respx.mock
def test_mysql_backup(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}/api/v1/backup/create").mock(
        return_value=httpx.Response(201, json={"message": "queued", "backup_id": 5})
    )
    result = runner.invoke(app, ["db", "mysql", "backup", "cluster-1"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "cluster-1" in body
    assert "mysql" in body  # database_type field


@respx.mock
def test_mysql_backups_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/backup/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": {"backups": [{"id": 5, "cluster_name": "c1"}]},
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "db", "mysql", "backups", "--cluster", "c1"])
    assert result.exit_code == 0
    # Inner data.backups list is what we emit
    assert '"id": 5' in result.stdout or '"id":5' in result.stdout


@respx.mock
def test_mysql_backup_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}/api/v1/backup/delete/5").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["db", "mysql", "backup-delete", "5", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_mysql_restore_with_yes(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}/api/v1/restore/initiate").mock(
        return_value=httpx.Response(200, json={"message": "restoring"})
    )
    result = runner.invoke(
        app,
        [
            "db",
            "mysql",
            "restore",
            "--backup-id",
            "5",
            "--target",
            "new-cluster",
            "--yes",
        ],
    )
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "new-cluster" in body
    assert "5" in body


@respx.mock
def test_mysql_restore_status(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/restore/status/5").mock(
        return_value=httpx.Response(200, json={"status": "in_progress"})
    )
    result = runner.invoke(app, ["--output", "json", "db", "mysql", "restore-status", "5"])
    assert result.exit_code == 0


# ---------- PostgreSQL: URL + schema differences ----------


@respx.mock
def test_pg_list_hits_postgres_router(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}/api/v1/postgres/all-postgres").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    result = runner.invoke(app, ["db", "pg", "list"])
    assert result.exit_code == 0


@respx.mock
def test_pg_create_uses_postgres_pass_field(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}/api/v1/postgres/create-postgres").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    result = runner.invoke(
        app,
        ["db", "pg", "create", "x", "--user", "u", "--password-stdin"],
        input="pw\n",
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "postgres_user" in body
    assert "postgres_pass" in body


@respx.mock
def test_pg_backup_uses_postgresql_type(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}/api/v1/backup/create").mock(
        return_value=httpx.Response(201, json={"message": "queued"})
    )
    runner.invoke(app, ["db", "pg", "backup", "cluster-pg"])
    body = route.calls.last.request.read().decode()
    assert "postgresql" in body


# ---------- MongoDB: type=mongodb param, no flavors, no region ----------


@respx.mock
def test_mongo_list_passes_type_query(logged_in: None, runner: CliRunner) -> None:
    route = respx.get(f"{BACKEND}/api/v1/database/all-databases").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    runner.invoke(app, ["db", "mongo", "list"])
    assert b"type=mongodb" in route.calls.last.request.url.query


@respx.mock
def test_mongo_create_uses_mongo_fields(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}/api/v1/database/create-deployment").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    result = runner.invoke(
        app,
        [
            "db",
            "mongo",
            "create",
            "m1",
            "--flavor",
            "M10",
            "--user",
            "admin",
            "--lts-version",
            "7.0",
            "--password-stdin",
        ],
        input="pw\n",
    )
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "mongo_user" in body
    assert "mongo_pass" in body
    assert "mongo_lts_version" in body
    assert "7.0" in body


@respx.mock
def test_mongo_scale_adds_type_field(logged_in: None, runner: CliRunner) -> None:
    route = respx.put(f"{BACKEND}/api/v1/database/scale-database/1").mock(
        return_value=httpx.Response(200, json={"message": "scaling"})
    )
    result = runner.invoke(app, ["db", "mongo", "scale", "1", "--flavor", "M20", "--yes"])
    assert result.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "mongodb" in body  # the scale endpoint dispatches on `type`


def test_mongo_has_no_flavors_command(runner: CliRunner) -> None:
    """MongoDB router doesn't expose /flavors, so the CLI shouldn't either."""
    result = runner.invoke(app, ["db", "mongo", "flavors"])
    # Typer returns 2 (usage error) for an unknown subcommand
    assert result.exit_code != 0


# ---------- error mapping ----------


_DB_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    # mysql
    ("GET", f"{BACKEND}/api/v1/mysql/all-mysql", ["db", "mysql", "list"]),
    (
        "GET",
        f"{BACKEND}/api/v1/mysql/status-mysql/1",
        ["db", "mysql", "status", "1"],
    ),
    ("GET", f"{BACKEND}/api/v1/mysql/flavors", ["db", "mysql", "flavors"]),
    (
        "DELETE",
        f"{BACKEND}/api/v1/mysql/delete-mysql/1",
        ["db", "mysql", "delete", "1", "--yes"],
    ),
    (
        "PUT",
        f"{BACKEND}/api/v1/mysql/scale-mysql/1",
        ["db", "mysql", "scale", "1", "--flavor", "X", "--yes"],
    ),
    (
        "POST",
        f"{BACKEND}/api/v1/backup/create",
        ["db", "mysql", "backup", "c1"],
    ),
    ("GET", f"{BACKEND}/api/v1/backup/list", ["db", "mysql", "backups"]),
    (
        "DELETE",
        f"{BACKEND}/api/v1/backup/delete/9",
        ["db", "mysql", "backup-delete", "9", "--yes"],
    ),
    (
        "POST",
        f"{BACKEND}/api/v1/restore/initiate",
        [
            "db",
            "mysql",
            "restore",
            "--backup-id",
            "9",
            "--target",
            "n",
            "--yes",
        ],
    ),
    (
        "GET",
        f"{BACKEND}/api/v1/restore/status/9",
        ["db", "mysql", "restore-status", "9"],
    ),
    # pg
    ("GET", f"{BACKEND}/api/v1/postgres/all-postgres", ["db", "pg", "list"]),
    # mongo
    ("GET", f"{BACKEND}/api/v1/database/all-databases", ["db", "mongo", "list"]),
    (
        "DELETE",
        f"{BACKEND}/api/v1/database/delete-database/1",
        ["db", "mongo", "delete", "1", "--yes"],
    ),
    (
        "PUT",
        f"{BACKEND}/api/v1/database/scale-database/1",
        ["db", "mongo", "scale", "1", "--flavor", "M20", "--yes"],
    ),
]


@pytest.mark.parametrize(("method", "url", "argv"), _DB_ERROR_PATHS)
@respx.mock
def test_db_command_500_returns_5(
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
