"""Tests for BlockStorageClient."""

from __future__ import annotations

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.block_storage import PREFIX, BlockStorageClient

BASE = "https://api.example.test"


def _client() -> BlockStorageClient:
    return BlockStorageClient(BaseClient(BASE, token="t"))


# ---------- volumes ----------


@respx.mock
def test_list_volumes_no_filters() -> None:
    respx.get(f"{BASE}{PREFIX}/volumes").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "v1"}], "message": "ok"}
        )
    )
    assert _client().list_volumes() == [{"id": "v1"}]


@respx.mock
def test_list_volumes_with_filters() -> None:
    route = respx.get(f"{BASE}{PREFIX}/volumes").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_volumes(status="available", name="data")
    qs = route.calls.last.request.url.query.decode()
    assert "status=available" in qs
    assert "name=data" in qs


@respx.mock
def test_create_volume_posts_body() -> None:
    route = respx.post(f"{BASE}{PREFIX}/volumes").mock(
        return_value=httpx.Response(201, json={"id": "v1", "name": "data", "size": 100})
    )
    _client().create_volume({"name": "data", "size": 100})
    body = route.calls.last.request.read().decode()
    assert "data" in body and "100" in body


@respx.mock
def test_get_volume() -> None:
    respx.get(f"{BASE}{PREFIX}/volumes/v1").mock(
        return_value=httpx.Response(200, json={"id": "v1"})
    )
    assert _client().get_volume("v1") == {"id": "v1"}


@respx.mock
def test_delete_volume() -> None:
    respx.delete(f"{BASE}{PREFIX}/volumes/v1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert _client().delete_volume("v1") == {"message": "deleted"}


@respx.mock
def test_attach_volume_with_device() -> None:
    route = respx.post(f"{BASE}{PREFIX}/volumes/v1/attach").mock(
        return_value=httpx.Response(200, json={"message": "attached"})
    )
    _client().attach_volume("v1", "srv-1", device="/dev/vdb")
    body = route.calls.last.request.read().decode()
    assert "srv-1" in body
    assert "/dev/vdb" in body


@respx.mock
def test_attach_volume_without_device_omits_field() -> None:
    route = respx.post(f"{BASE}{PREFIX}/volumes/v1/attach").mock(
        return_value=httpx.Response(200, json={"message": "attached"})
    )
    _client().attach_volume("v1", "srv-1")
    body = route.calls.last.request.read().decode()
    assert "device" not in body


@respx.mock
def test_detach_volume() -> None:
    route = respx.post(f"{BASE}{PREFIX}/volumes/v1/detach").mock(
        return_value=httpx.Response(200, json={"message": "detached"})
    )
    _client().detach_volume("v1", "srv-1")
    body = route.calls.last.request.read().decode()
    assert "srv-1" in body


# ---------- snapshots ----------


@respx.mock
def test_list_snapshots_no_filter() -> None:
    respx.get(f"{BASE}{PREFIX}/snapshots").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "s1"}], "message": "ok"}
        )
    )
    assert _client().list_snapshots() == [{"id": "s1"}]


@respx.mock
def test_list_snapshots_with_volume_filter() -> None:
    route = respx.get(f"{BASE}{PREFIX}/snapshots").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_snapshots(volume_id="v1")
    assert b"volume_id=v1" in route.calls.last.request.url.query


@respx.mock
def test_create_snapshot() -> None:
    route = respx.post(f"{BASE}{PREFIX}/snapshots").mock(
        return_value=httpx.Response(201, json={"id": "s1"})
    )
    _client().create_snapshot({"volume_id": "v1", "name": "snap"})
    body = route.calls.last.request.read().decode()
    assert "v1" in body and "snap" in body


@respx.mock
def test_get_snapshot() -> None:
    respx.get(f"{BASE}{PREFIX}/snapshots/s1").mock(
        return_value=httpx.Response(200, json={"id": "s1"})
    )
    assert _client().get_snapshot("s1") == {"id": "s1"}


@respx.mock
def test_delete_snapshot() -> None:
    respx.delete(f"{BASE}{PREFIX}/snapshots/s1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert _client().delete_snapshot("s1") == {"message": "deleted"}


@respx.mock
def test_list_returns_empty_when_response_not_list() -> None:
    respx.get(f"{BASE}{PREFIX}/volumes").mock(
        return_value=httpx.Response(200, json={"status": False})
    )
    assert _client().list_volumes() == []
