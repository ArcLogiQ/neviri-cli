"""Tests for ComputeClient: thin pass-through over BaseClient."""

from __future__ import annotations

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.compute import PREFIX, ComputeClient

BASE = "https://api.example.test"


def _client() -> ComputeClient:
    return ComputeClient(BaseClient(BASE, token="t"))


@respx.mock
def test_list_servers_no_filters() -> None:
    route = respx.get(f"{BASE}{PREFIX}/servers").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "a"}], "message": "ok"}
        )
    )
    assert _client().list_servers() == [{"id": "a"}]
    # No query string when no filters
    assert route.calls.last.request.url.query in (b"", b"None")


@respx.mock
def test_list_servers_passes_filters_as_query() -> None:
    route = respx.get(f"{BASE}{PREFIX}/servers").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_servers(status="ACTIVE", name="web")
    qs = route.calls.last.request.url.query.decode()
    assert "status=ACTIVE" in qs
    assert "name=web" in qs


@respx.mock
def test_get_server() -> None:
    respx.get(f"{BASE}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"id": "abc", "name": "web"})
    )
    assert _client().get_server("abc") == {"id": "abc", "name": "web"}


@respx.mock
def test_create_server_posts_body() -> None:
    route = respx.post(f"{BASE}{PREFIX}/servers").mock(
        return_value=httpx.Response(201, json={"id": "new", "name": "web"})
    )
    body = {"name": "web", "flavor_id": "f1", "image_id": "i1", "network_id": "n1"}
    assert _client().create_server(body) == {"id": "new", "name": "web"}
    sent = route.calls.last.request.read().decode()
    assert "flavor_id" in sent
    assert "n1" in sent


@respx.mock
def test_delete_server_no_force_omits_param() -> None:
    route = respx.delete(f"{BASE}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_server("abc")
    assert route.calls.last.request.url.query == b""


@respx.mock
def test_delete_server_force_passes_query() -> None:
    route = respx.delete(f"{BASE}{PREFIX}/servers/abc").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_server("abc", force=True)
    assert route.calls.last.request.url.query == b"force=true"


@respx.mock
def test_server_action_start() -> None:
    route = respx.post(f"{BASE}{PREFIX}/servers/abc/action").mock(
        return_value=httpx.Response(200, json={"message": "started"})
    )
    _client().server_action("abc", "start")
    sent = route.calls.last.request.read().decode()
    assert '"action": "start"' in sent or '"action":"start"' in sent
    # No reboot_type when not provided
    assert "reboot_type" not in sent


@respx.mock
def test_server_action_reboot_includes_type() -> None:
    route = respx.post(f"{BASE}{PREFIX}/servers/abc/action").mock(
        return_value=httpx.Response(200, json={"message": "rebooting"})
    )
    _client().server_action("abc", "reboot", reboot_type="HARD")
    sent = route.calls.last.request.read().decode()
    assert "HARD" in sent


@respx.mock
def test_resize_server() -> None:
    route = respx.post(f"{BASE}{PREFIX}/servers/abc/resize").mock(
        return_value=httpx.Response(200, json={"message": "resizing"})
    )
    _client().resize_server("abc", "f-large")
    sent = route.calls.last.request.read().decode()
    assert "f-large" in sent


@respx.mock
def test_resize_confirm_and_revert() -> None:
    respx.post(f"{BASE}{PREFIX}/servers/abc/resize/confirm").mock(
        return_value=httpx.Response(200, json={"message": "confirmed"})
    )
    respx.post(f"{BASE}{PREFIX}/servers/abc/resize/revert").mock(
        return_value=httpx.Response(200, json={"message": "reverted"})
    )
    assert _client().confirm_resize("abc") == {"message": "confirmed"}
    assert _client().revert_resize("abc") == {"message": "reverted"}


@respx.mock
def test_get_console_default_type() -> None:
    route = respx.get(f"{BASE}{PREFIX}/servers/abc/console").mock(
        return_value=httpx.Response(200, json={"console_type": "novnc", "url": "https://vnc.x"})
    )
    result = _client().get_console("abc")
    assert result["url"] == "https://vnc.x"
    assert b"console_type=novnc" in route.calls.last.request.url.query


@respx.mock
def test_get_console_custom_type() -> None:
    route = respx.get(f"{BASE}{PREFIX}/servers/abc/console").mock(
        return_value=httpx.Response(200, json={"console_type": "spice-html5", "url": "https://x"})
    )
    _client().get_console("abc", console_type="spice-html5")
    assert b"console_type=spice-html5" in route.calls.last.request.url.query


@respx.mock
def test_list_flavors() -> None:
    respx.get(f"{BASE}{PREFIX}/flavors").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "f1", "name": "m1.small"}], "message": "ok"}
        )
    )
    assert _client().list_flavors() == [{"id": "f1", "name": "m1.small"}]


@respx.mock
def test_list_images() -> None:
    respx.get(f"{BASE}{PREFIX}/images").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "i1", "name": "ubuntu"}], "message": "ok"}
        )
    )
    assert _client().list_images() == [{"id": "i1", "name": "ubuntu"}]


@respx.mock
def test_list_returns_empty_when_response_is_dict() -> None:
    """If the backend returns a non-list (defensive), we don't crash."""
    respx.get(f"{BASE}{PREFIX}/servers").mock(
        return_value=httpx.Response(200, json={"status": False, "message": "no perms"})
    )
    assert _client().list_servers() == []


@respx.mock
def test_create_returns_empty_dict_when_response_is_list() -> None:
    """Defensive: non-dict response on a creation endpoint."""
    respx.post(f"{BASE}{PREFIX}/servers").mock(return_value=httpx.Response(201, json=[1, 2, 3]))
    assert _client().create_server({}) == {}
