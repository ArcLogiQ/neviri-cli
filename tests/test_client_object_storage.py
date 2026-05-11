"""Tests for ObjectStorageClient."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.object_storage import PREFIX, ObjectStorageClient, _CallbackReader

BASE = "https://api.example.test"


def _client() -> ObjectStorageClient:
    return ObjectStorageClient(BaseClient(BASE, token="t"))


# ---------- buckets ----------


@respx.mock
def test_list_buckets() -> None:
    respx.get(f"{BASE}{PREFIX}/containers").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "data": [{"name": "b1", "count": 5, "bytes": 1024}],
                "message": "ok",
            },
        )
    )
    assert _client().list_buckets() == [{"name": "b1", "count": 5, "bytes": 1024}]


@respx.mock
def test_create_bucket_without_metadata() -> None:
    route = respx.post(f"{BASE}{PREFIX}/containers").mock(
        return_value=httpx.Response(201, json={"name": "b1"})
    )
    _client().create_bucket("b1")
    body = route.calls.last.request.read().decode()
    assert "b1" in body
    assert "metadata" not in body


@respx.mock
def test_create_bucket_with_metadata() -> None:
    route = respx.post(f"{BASE}{PREFIX}/containers").mock(
        return_value=httpx.Response(201, json={"name": "b1"})
    )
    _client().create_bucket("b1", metadata={"env": "prod"})
    body = route.calls.last.request.read().decode()
    assert "env" in body and "prod" in body


@respx.mock
def test_get_bucket() -> None:
    respx.get(f"{BASE}{PREFIX}/containers/b1").mock(
        return_value=httpx.Response(200, json={"name": "b1", "count": 2})
    )
    assert _client().get_bucket("b1")["name"] == "b1"


@respx.mock
def test_delete_bucket() -> None:
    respx.delete(f"{BASE}{PREFIX}/containers/b1").mock(
        return_value=httpx.Response(200, json={"message": "Container 'b1' deleted"})
    )
    assert "deleted" in _client().delete_bucket("b1")["message"]


# ---------- objects: list ----------


@respx.mock
def test_list_objects() -> None:
    respx.get(f"{BASE}{PREFIX}/containers/b1/objects").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"name": "a.txt", "bytes": 12}], "message": "ok"},
        )
    )
    assert _client().list_objects("b1") == [{"name": "a.txt", "bytes": 12}]


@respx.mock
def test_list_objects_with_prefix() -> None:
    route = respx.get(f"{BASE}{PREFIX}/containers/b1/objects").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_objects("b1", prefix="2026-05/")
    assert b"prefix=2026-05" in route.calls.last.request.url.query


# ---------- objects: upload ----------


@respx.mock
def test_upload_object_sends_multipart(tmp_path: Path) -> None:
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")

    route = respx.put(f"{BASE}{PREFIX}/containers/b1/objects/data.bin").mock(
        return_value=httpx.Response(
            200, json={"container": "b1", "name": "data.bin", "etag": "abc"}
        )
    )
    result = _client().upload_object("b1", "data.bin", f)
    assert result["etag"] == "abc"

    request = route.calls.last.request
    content_type = request.headers.get("content-type", "")
    assert content_type.startswith("multipart/form-data")
    body = request.read()
    # The file payload appears in the multipart body
    assert b"hello world" in body
    assert b"data.bin" in body


@respx.mock
def test_upload_object_progress_callback_fires(tmp_path: Path) -> None:
    f = tmp_path / "data.bin"
    f.write_bytes(b"X" * 4096)

    respx.put(f"{BASE}{PREFIX}/containers/b1/objects/data.bin").mock(
        return_value=httpx.Response(200, json={"etag": "x"})
    )

    advances: list[int] = []

    def cb(n: int) -> None:
        advances.append(n)

    _client().upload_object("b1", "data.bin", f, on_progress=cb)

    # File is non-trivial size, so at least one chunk should have fired.
    assert advances, "expected at least one progress callback"
    assert sum(advances) == 4096


@respx.mock
def test_upload_uses_custom_content_type(tmp_path: Path) -> None:
    f = tmp_path / "x.json"
    f.write_text("{}")
    route = respx.put(f"{BASE}{PREFIX}/containers/b1/objects/x.json").mock(
        return_value=httpx.Response(200, json={"etag": "j"})
    )
    _client().upload_object("b1", "x.json", f, content_type="application/json")
    body = route.calls.last.request.read()
    assert b"application/json" in body


# ---------- objects: download ----------


@respx.mock
def test_download_object_writes_to_disk(tmp_path: Path) -> None:
    payload = b"some-binary-data" * 64
    respx.get(f"{BASE}{PREFIX}/containers/b1/objects/file.bin").mock(
        return_value=httpx.Response(200, content=payload)
    )

    dest = tmp_path / "out.bin"
    written = _client().download_object("b1", "file.bin", dest)
    assert dest.read_bytes() == payload
    assert written == len(payload)


@respx.mock
def test_download_object_progress_callback_fires(tmp_path: Path) -> None:
    respx.get(f"{BASE}{PREFIX}/containers/b1/objects/file.bin").mock(
        return_value=httpx.Response(200, content=b"X" * 8192)
    )
    advances: list[int] = []
    _client().download_object("b1", "file.bin", tmp_path / "out.bin", on_progress=advances.append)
    assert advances
    assert sum(advances) == 8192


@respx.mock
def test_download_object_creates_parent_dirs(tmp_path: Path) -> None:
    respx.get(f"{BASE}{PREFIX}/containers/b1/objects/file.bin").mock(
        return_value=httpx.Response(200, content=b"hi")
    )
    dest = tmp_path / "new" / "deeper" / "out.bin"
    _client().download_object("b1", "file.bin", dest)
    assert dest.exists()


@respx.mock
def test_download_object_404_raises_user_error(tmp_path: Path) -> None:
    from neviri_cli.exceptions import UserError

    respx.get(f"{BASE}{PREFIX}/containers/b1/objects/missing").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    with pytest.raises(UserError):
        _client().download_object("b1", "missing", tmp_path / "out.bin")


# ---------- objects: delete ----------


@respx.mock
def test_delete_object() -> None:
    respx.delete(f"{BASE}{PREFIX}/containers/b1/objects/x.txt").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert "deleted" in _client().delete_object("b1", "x.txt")["message"]


# ---------- _CallbackReader wrapper ----------


def test_callback_reader_fires_on_each_read(tmp_path: Path) -> None:
    f = tmp_path / "x"
    f.write_bytes(b"abcdef")
    advances: list[int] = []
    with f.open("rb") as raw:
        reader = _CallbackReader(raw, advances.append)
        # Read a partial chunk, then read the rest.
        assert reader.read(2) == b"ab"
        assert reader.read() == b"cdef"
    assert advances == [2, 4]


def test_callback_reader_does_not_fire_on_empty_read(tmp_path: Path) -> None:
    f = tmp_path / "x"
    f.write_bytes(b"")
    advances: list[int] = []
    with f.open("rb") as raw:
        reader = _CallbackReader(raw, advances.append)
        assert reader.read() == b""
    assert advances == []
