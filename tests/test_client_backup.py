"""Tests for BackupClient (backup + restore)."""

from __future__ import annotations

import httpx
import respx

from neviri_cli.client.backup import BACKUP_PREFIX, RESTORE_PREFIX, BackupClient
from neviri_cli.client.base import BaseClient

BASE = "https://api.example.test"


def _client() -> BackupClient:
    return BackupClient(BaseClient(BASE, token="t"))


@respx.mock
def test_create_backup_sends_cluster_and_type() -> None:
    route = respx.post(f"{BASE}{BACKUP_PREFIX}/create").mock(
        return_value=httpx.Response(201, json={"message": "queued", "backup_id": 1})
    )
    _client().create_backup(cluster_name="cluster-1", database_type="mysql")
    body = route.calls.last.request.read().decode()
    assert "cluster-1" in body and "mysql" in body


@respx.mock
def test_list_backups_no_filter() -> None:
    respx.get(f"{BASE}{BACKUP_PREFIX}/list").mock(
        return_value=httpx.Response(200, json={"status": True, "data": {"backups": [{"id": 1}]}})
    )
    result = _client().list_backups()
    assert result["data"]["backups"] == [{"id": 1}]


@respx.mock
def test_list_backups_with_cluster_filter_uses_camel_case_param() -> None:
    route = respx.get(f"{BASE}{BACKUP_PREFIX}/list").mock(
        return_value=httpx.Response(200, json={"status": True, "data": {"backups": []}})
    )
    _client().list_backups(cluster_name="my-cluster")
    qs = route.calls.last.request.url.query.decode()
    assert "clusterName=my-cluster" in qs


@respx.mock
def test_get_backup() -> None:
    respx.get(f"{BASE}{BACKUP_PREFIX}/details/9").mock(
        return_value=httpx.Response(200, json={"id": 9, "size": "100MB"})
    )
    assert _client().get_backup(9)["id"] == 9


@respx.mock
def test_delete_backup() -> None:
    respx.delete(f"{BASE}{BACKUP_PREFIX}/delete/9").mock(
        return_value=httpx.Response(200, json={"status": True, "message": "deleted"})
    )
    _client().delete_backup(9)


@respx.mock
def test_download_backup_url() -> None:
    respx.get(f"{BASE}{BACKUP_PREFIX}/download/9").mock(
        return_value=httpx.Response(200, json={"download_url": "https://s3.x/abc"})
    )
    result = _client().download_backup(9)
    assert result["download_url"].startswith("https://")


@respx.mock
def test_initiate_restore() -> None:
    route = respx.post(f"{BASE}{RESTORE_PREFIX}/initiate").mock(
        return_value=httpx.Response(200, json={"message": "restoring"})
    )
    _client().initiate_restore(backup_id=9, target_cluster_name="new")
    body = route.calls.last.request.read().decode()
    assert "new" in body and "9" in body


@respx.mock
def test_initiate_restore_with_options() -> None:
    route = respx.post(f"{BASE}{RESTORE_PREFIX}/initiate").mock(
        return_value=httpx.Response(200, json={"message": "restoring"})
    )
    _client().initiate_restore(
        backup_id=9,
        target_cluster_name="new",
        restore_options={"drop_existing": True},
    )
    body = route.calls.last.request.read().decode()
    assert "drop_existing" in body


@respx.mock
def test_restore_status() -> None:
    respx.get(f"{BASE}{RESTORE_PREFIX}/status/9").mock(
        return_value=httpx.Response(200, json={"status": "in_progress"})
    )
    assert _client().get_restore_status(9)["status"] == "in_progress"


@respx.mock
def test_cancel_restore() -> None:
    respx.post(f"{BASE}{RESTORE_PREFIX}/cancel/9").mock(
        return_value=httpx.Response(200, json={"message": "cancelled"})
    )
    _client().cancel_restore(9)
