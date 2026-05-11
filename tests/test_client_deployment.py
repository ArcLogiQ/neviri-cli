"""Tests for DeploymentClient."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.deployment import APPS_PREFIX, DEPLOYMENTS_PREFIX, DeploymentClient

BASE = "https://api.example.test"


def _client() -> DeploymentClient:
    return DeploymentClient(BaseClient(BASE, token="t"))


# ---------- apps ----------


@respx.mock
def test_list_apps() -> None:
    respx.get(f"{BASE}{APPS_PREFIX}/").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 1, "name": "web"}], "message": "ok"}
        )
    )
    assert _client().list_apps() == [{"id": 1, "name": "web"}]


@respx.mock
def test_create_app_sends_name() -> None:
    route = respx.post(f"{BASE}{APPS_PREFIX}/").mock(
        return_value=httpx.Response(201, json={"id": 1, "name": "web"})
    )
    _client().create_app("web")
    body = route.calls.last.request.read().decode()
    assert '"name": "web"' in body or '"name":"web"' in body


@respx.mock
def test_get_app() -> None:
    respx.get(f"{BASE}{APPS_PREFIX}/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "web"})
    )
    assert _client().get_app(1)["name"] == "web"


@respx.mock
def test_delete_app() -> None:
    respx.delete(f"{BASE}{APPS_PREFIX}/1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_app(1)


@respx.mock
def test_list_deployments() -> None:
    respx.get(f"{BASE}{APPS_PREFIX}/1/deployments").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 10}], "message": "ok"}
        )
    )
    assert _client().list_deployments(1) == [{"id": 10}]


# ---------- upload ----------


@respx.mock
def test_upload_zip_sends_multipart(tmp_path: Path) -> None:
    zip_path = tmp_path / "app.zip"
    zip_path.write_bytes(b"PK\x03\x04fake-zip-data")

    route = respx.post(f"{BASE}{APPS_PREFIX}/1/upload").mock(
        return_value=httpx.Response(201, json={"id": 10, "build_status": "pending"})
    )
    result = _client().upload_zip(1, zip_path)
    assert result["id"] == 10

    request = route.calls.last.request
    assert request.headers.get("content-type", "").startswith("multipart/form-data")
    body = request.read()
    assert b"PK\x03\x04" in body
    assert b"app.zip" in body


@respx.mock
def test_upload_zip_progress_callback(tmp_path: Path) -> None:
    zip_path = tmp_path / "big.zip"
    zip_path.write_bytes(b"X" * 4096)
    respx.post(f"{BASE}{APPS_PREFIX}/1/upload").mock(
        return_value=httpx.Response(201, json={"id": 10})
    )
    advances: list[int] = []
    _client().upload_zip(1, zip_path, on_progress=advances.append)
    assert sum(advances) == 4096


# ---------- env vars ----------


@respx.mock
def test_list_env_variables() -> None:
    respx.get(f"{BASE}{APPS_PREFIX}/1/env").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"id": 5, "key": "K", "value": "V"}], "message": "ok"},
        )
    )
    assert _client().list_env_variables(1) == [{"id": 5, "key": "K", "value": "V"}]


@respx.mock
def test_add_env_variable() -> None:
    route = respx.post(f"{BASE}{APPS_PREFIX}/1/env").mock(
        return_value=httpx.Response(201, json={"id": 5})
    )
    _client().add_env_variable(1, "DATABASE_URL", "postgres://x")
    body = route.calls.last.request.read().decode()
    assert "DATABASE_URL" in body
    assert "postgres://x" in body


@respx.mock
def test_delete_env_variable() -> None:
    respx.delete(f"{BASE}{APPS_PREFIX}/1/env/5").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_env_variable(1, 5)


# ---------- deployment stages ----------


@respx.mock
def test_get_deployment() -> None:
    respx.get(f"{BASE}{DEPLOYMENTS_PREFIX}/10").mock(
        return_value=httpx.Response(200, json={"id": 10, "build_status": "succeeded"})
    )
    assert _client().get_deployment(10)["build_status"] == "succeeded"


@respx.mock
def test_get_manifests() -> None:
    respx.get(f"{BASE}{DEPLOYMENTS_PREFIX}/10/manifests").mock(
        return_value=httpx.Response(
            200,
            json={
                "deployment_manifest": "kind: Deployment",
                "service_manifest": "kind: Service",
                "ingress_manifest": "kind: Ingress",
            },
        )
    )
    result = _client().get_manifests(10)
    assert "Deployment" in result["deployment_manifest"]


@respx.mock
def test_trigger_build() -> None:
    respx.post(f"{BASE}{DEPLOYMENTS_PREFIX}/10/build").mock(
        return_value=httpx.Response(202, json={"message": "build triggered"})
    )
    _client().trigger_build(10)


@respx.mock
def test_trigger_deploy() -> None:
    respx.post(f"{BASE}{DEPLOYMENTS_PREFIX}/10/deploy").mock(
        return_value=httpx.Response(202, json={"message": "deploy triggered"})
    )
    _client().trigger_deploy(10)


@respx.mock
def test_trigger_service() -> None:
    respx.post(f"{BASE}{DEPLOYMENTS_PREFIX}/10/service").mock(
        return_value=httpx.Response(202, json={"message": "service triggered"})
    )
    _client().trigger_service(10)


@respx.mock
def test_trigger_ingress() -> None:
    respx.post(f"{BASE}{DEPLOYMENTS_PREFIX}/10/ingress").mock(
        return_value=httpx.Response(202, json={"message": "ingress triggered"})
    )
    _client().trigger_ingress(10)
