"""End-to-end tests for `neviri app` and `neviri deploy`."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token

BACKEND = "http://localhost:8000"
APPS = "/api/v1/apps"
DEPLOYMENTS = "/api/v1/deployments"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


# ============================================================
# neviri app
# ============================================================


@respx.mock
def test_app_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{APPS}/").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"id": 1, "name": "web"}], "message": "ok"},
        )
    )
    result = runner.invoke(app, ["--output", "json", "app", "list"])
    assert result.exit_code == 0
    assert "web" in result.stdout


@respx.mock
def test_app_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{APPS}/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "web"})
    )
    result = runner.invoke(app, ["--output", "json", "app", "get", "1"])
    assert result.exit_code == 0


@respx.mock
def test_app_create(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{APPS}/").mock(
        return_value=httpx.Response(201, json={"id": 1, "name": "web"})
    )
    result = runner.invoke(app, ["app", "create", "web"])
    assert result.exit_code == 0
    assert "web" in route.calls.last.request.read().decode()


@respx.mock
def test_app_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{APPS}/1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["app", "delete", "1", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_app_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{APPS}/1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["app", "delete", "1"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


@respx.mock
def test_app_deployments(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{APPS}/1/deployments").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 10}], "message": "ok"}
        )
    )
    result = runner.invoke(app, ["--output", "json", "app", "deployments", "1"])
    assert result.exit_code == 0
    assert "10" in result.stdout


# ---------- upload ----------


@respx.mock
def test_app_upload_zip(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    zip_path = tmp_path / "myapp.zip"
    zip_path.write_bytes(b"PK\x03\x04binary-payload")

    route = respx.post(f"{BACKEND}{APPS}/1/upload").mock(
        return_value=httpx.Response(201, json={"id": 10, "build_status": "pending"})
    )
    result = runner.invoke(app, ["app", "upload", "1", "--file", str(zip_path), "--no-progress"])
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read()
    assert b"PK\x03\x04" in body
    assert b"myapp.zip" in body


@respx.mock
def test_app_upload_rejects_non_zip(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    other = tmp_path / "myapp.tar.gz"
    other.write_bytes(b"not-a-zip")
    result = runner.invoke(app, ["app", "upload", "1", "--file", str(other), "--no-progress"])
    assert result.exit_code == 2


# ---------- env vars ----------


@respx.mock
def test_app_env_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{APPS}/1/env").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 5, "key": "K"}], "message": "ok"}
        )
    )
    result = runner.invoke(app, ["--output", "json", "app", "env-list", "1"])
    assert result.exit_code == 0


@respx.mock
def test_app_env_set(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{APPS}/1/env").mock(
        return_value=httpx.Response(201, json={"id": 5, "key": "DB_URL"})
    )
    result = runner.invoke(app, ["app", "env-set", "1", "DB_URL=postgres://x"])
    assert result.exit_code == 0, result.stdout
    body = route.calls.last.request.read().decode()
    assert "DB_URL" in body and "postgres://x" in body


def test_app_env_set_rejects_bad_format(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "test-token")
    result = runner.invoke(app, ["app", "env-set", "1", "no-equals-sign"])
    assert result.exit_code == 2


def test_app_env_set_rejects_empty_key(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "test-token")
    result = runner.invoke(app, ["app", "env-set", "1", "=value"])
    assert result.exit_code == 2


@respx.mock
def test_app_env_unset(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{APPS}/1/env/5").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    result = runner.invoke(app, ["app", "env-unset", "1", "5"])
    assert result.exit_code == 0


# ============================================================
# neviri deploy
# ============================================================


@respx.mock
def test_deploy_get(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{DEPLOYMENTS}/10").mock(
        return_value=httpx.Response(200, json={"id": 10, "build_status": "succeeded"})
    )
    result = runner.invoke(app, ["--output", "json", "deploy", "get", "10"])
    assert result.exit_code == 0


@respx.mock
def test_deploy_manifests(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{DEPLOYMENTS}/10/manifests").mock(
        return_value=httpx.Response(
            200,
            json={
                "deployment_manifest": "kind: Deployment",
                "service_manifest": "kind: Service",
                "ingress_manifest": "kind: Ingress",
            },
        )
    )
    result = runner.invoke(app, ["--output", "yaml", "deploy", "manifests", "10"])
    assert result.exit_code == 0
    assert "Deployment" in result.stdout


@respx.mock
def test_deploy_stages_individually(logged_in: None, runner: CliRunner) -> None:
    for stage in ("build", "deploy", "service", "ingress"):
        respx.post(f"{BACKEND}{DEPLOYMENTS}/10/{stage}").mock(
            return_value=httpx.Response(202, json={"message": f"{stage} triggered"})
        )
    assert runner.invoke(app, ["deploy", "build", "10"]).exit_code == 0
    assert runner.invoke(app, ["deploy", "deploy", "10"]).exit_code == 0
    assert runner.invoke(app, ["deploy", "service", "10"]).exit_code == 0
    assert runner.invoke(app, ["deploy", "ingress", "10"]).exit_code == 0


@respx.mock
def test_deploy_run_triggers_all_four_stages(logged_in: None, runner: CliRunner) -> None:
    build = respx.post(f"{BACKEND}{DEPLOYMENTS}/10/build").mock(
        return_value=httpx.Response(202, json={"message": "ok"})
    )
    deploy = respx.post(f"{BACKEND}{DEPLOYMENTS}/10/deploy").mock(
        return_value=httpx.Response(202, json={"message": "ok"})
    )
    service = respx.post(f"{BACKEND}{DEPLOYMENTS}/10/service").mock(
        return_value=httpx.Response(202, json={"message": "ok"})
    )
    ingress = respx.post(f"{BACKEND}{DEPLOYMENTS}/10/ingress").mock(
        return_value=httpx.Response(202, json={"message": "ok"})
    )
    result = runner.invoke(app, ["--output", "json", "deploy", "run", "10"])
    assert result.exit_code == 0, result.stdout
    assert build.call_count == 1
    assert deploy.call_count == 1
    assert service.call_count == 1
    assert ingress.call_count == 1


# ---------- logs ----------


@respx.mock
def test_deploy_logs_one_shot(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{DEPLOYMENTS}/10").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 10,
                "build_status": "succeeded",
                "build_log": "line 1\nline 2\nline 3",
            },
        )
    )
    result = runner.invoke(app, ["deploy", "logs", "10"])
    assert result.exit_code == 0
    assert "line 1" in result.stdout
    assert "line 3" in result.stdout


@respx.mock
def test_deploy_logs_tail(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{DEPLOYMENTS}/10").mock(
        return_value=httpx.Response(
            200,
            json={
                "build_log": "line 1\nline 2\nline 3\nline 4\nline 5",
            },
        )
    )
    result = runner.invoke(app, ["deploy", "logs", "10", "--tail", "2"])
    assert result.exit_code == 0
    assert "line 5" in result.stdout
    assert "line 4" in result.stdout
    assert "line 1" not in result.stdout


@respx.mock
def test_deploy_logs_follow_stops_when_done(logged_in: None, runner: CliRunner) -> None:
    """`-f` polls until all stages report succeeded/failed/error."""
    # First call: in-progress with 1 line.
    # Second call: succeeded with 2 lines (so one new line is printed).
    respx.get(f"{BACKEND}{DEPLOYMENTS}/10").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": 10,
                    "build_status": "in_progress",
                    "deploy_status": "pending",
                    "service_status": "pending",
                    "ingress_status": "pending",
                    "build_log": "line 1",
                },
            ),
            httpx.Response(
                200,
                json={
                    "id": 10,
                    "build_status": "succeeded",
                    "deploy_status": "succeeded",
                    "service_status": "succeeded",
                    "ingress_status": "succeeded",
                    "build_log": "line 1\nline 2",
                },
            ),
        ]
    )
    result = runner.invoke(app, ["deploy", "logs", "10", "--follow", "--interval", "0.5"])
    assert result.exit_code == 0, result.stdout
    assert "line 1" in result.stdout
    assert "line 2" in result.stdout


# ---------- rollback (intentionally errors) ----------


def test_deploy_rollback_returns_2_with_explanation(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "test-token")
    result = runner.invoke(app, ["deploy", "rollback", "10"])
    assert result.exit_code == 2
    assert "rollback is not implemented" in result.stderr


# ---------- error mapping ----------


_AD_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    ("GET", f"{BACKEND}{APPS}/", ["app", "list"]),
    ("GET", f"{BACKEND}{APPS}/1", ["app", "get", "1"]),
    ("POST", f"{BACKEND}{APPS}/", ["app", "create", "x"]),
    ("DELETE", f"{BACKEND}{APPS}/1", ["app", "delete", "1", "--yes"]),
    ("GET", f"{BACKEND}{APPS}/1/deployments", ["app", "deployments", "1"]),
    ("GET", f"{BACKEND}{APPS}/1/env", ["app", "env-list", "1"]),
    ("POST", f"{BACKEND}{APPS}/1/env", ["app", "env-set", "1", "K=V"]),
    ("DELETE", f"{BACKEND}{APPS}/1/env/5", ["app", "env-unset", "1", "5"]),
    ("GET", f"{BACKEND}{DEPLOYMENTS}/10", ["deploy", "get", "10"]),
    ("GET", f"{BACKEND}{DEPLOYMENTS}/10/manifests", ["deploy", "manifests", "10"]),
    ("POST", f"{BACKEND}{DEPLOYMENTS}/10/build", ["deploy", "build", "10"]),
    ("POST", f"{BACKEND}{DEPLOYMENTS}/10/deploy", ["deploy", "deploy", "10"]),
    ("POST", f"{BACKEND}{DEPLOYMENTS}/10/service", ["deploy", "service", "10"]),
    ("POST", f"{BACKEND}{DEPLOYMENTS}/10/ingress", ["deploy", "ingress", "10"]),
]


@pytest.mark.parametrize(("method", "url", "argv"), _AD_ERROR_PATHS)
@respx.mock
def test_app_deploy_command_500_returns_5(
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
