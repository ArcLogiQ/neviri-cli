"""Tests for LoadBalancerClient."""

from __future__ import annotations

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.load_balancer import PREFIX, LoadBalancerClient

BASE = "https://api.example.test"


def _client() -> LoadBalancerClient:
    return LoadBalancerClient(BaseClient(BASE, token="t"))


# ---------- load balancers ----------


@respx.mock
def test_list_lbs() -> None:
    respx.get(f"{BASE}{PREFIX}").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "lb-1"}], "message": "ok"}
        )
    )
    assert _client().list_load_balancers() == [{"id": "lb-1"}]


@respx.mock
def test_list_lbs_with_name_filter() -> None:
    route = respx.get(f"{BASE}{PREFIX}").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_load_balancers(name="web")
    assert b"name=web" in route.calls.last.request.url.query


@respx.mock
def test_create_lb() -> None:
    respx.post(f"{BASE}{PREFIX}").mock(return_value=httpx.Response(201, json={"id": "lb-1"}))
    _client().create_load_balancer({"name": "x", "vip_subnet_id": "s1"})


@respx.mock
def test_get_lb() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1").mock(return_value=httpx.Response(200, json={"id": "lb-1"}))
    assert _client().get_load_balancer("lb-1")["id"] == "lb-1"


@respx.mock
def test_update_lb() -> None:
    respx.put(f"{BASE}{PREFIX}/lb-1").mock(return_value=httpx.Response(200, json={"id": "lb-1"}))
    _client().update_load_balancer("lb-1", {"name": "renamed"})


@respx.mock
def test_delete_lb_no_cascade() -> None:
    route = respx.delete(f"{BASE}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"message": "deleting"})
    )
    _client().delete_load_balancer("lb-1")
    assert route.calls.last.request.url.query == b""


@respx.mock
def test_delete_lb_cascade() -> None:
    route = respx.delete(f"{BASE}{PREFIX}/lb-1").mock(
        return_value=httpx.Response(200, json={"message": "deleting"})
    )
    _client().delete_load_balancer("lb-1", cascade=True)
    assert b"cascade=true" in route.calls.last.request.url.query


# ---------- listeners ----------


@respx.mock
def test_list_listeners() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/listeners").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "ls-1"}], "message": "ok"}
        )
    )
    assert _client().list_listeners("lb-1") == [{"id": "ls-1"}]


@respx.mock
def test_create_listener() -> None:
    route = respx.post(f"{BASE}{PREFIX}/lb-1/listeners").mock(
        return_value=httpx.Response(201, json={"id": "ls-1"})
    )
    _client().create_listener("lb-1", {"name": "http", "protocol": "HTTP", "protocol_port": 80})
    body = route.calls.last.request.read().decode()
    assert "HTTP" in body
    assert "80" in body


@respx.mock
def test_get_listener() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/listeners/ls-1").mock(
        return_value=httpx.Response(200, json={"id": "ls-1"})
    )
    _client().get_listener("lb-1", "ls-1")


@respx.mock
def test_delete_listener() -> None:
    respx.delete(f"{BASE}{PREFIX}/lb-1/listeners/ls-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_listener("lb-1", "ls-1")


# ---------- pools ----------


@respx.mock
def test_list_pools() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/pools").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "p-1"}], "message": "ok"}
        )
    )
    assert _client().list_pools("lb-1") == [{"id": "p-1"}]


@respx.mock
def test_create_pool() -> None:
    route = respx.post(f"{BASE}{PREFIX}/lb-1/pools").mock(
        return_value=httpx.Response(201, json={"id": "p-1"})
    )
    _client().create_pool(
        "lb-1", {"name": "web", "protocol": "HTTP", "lb_algorithm": "ROUND_ROBIN"}
    )
    body = route.calls.last.request.read().decode()
    assert "ROUND_ROBIN" in body


@respx.mock
def test_get_pool() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/pools/p-1").mock(
        return_value=httpx.Response(200, json={"id": "p-1"})
    )
    _client().get_pool("lb-1", "p-1")


@respx.mock
def test_delete_pool() -> None:
    respx.delete(f"{BASE}{PREFIX}/lb-1/pools/p-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_pool("lb-1", "p-1")


# ---------- members ----------


@respx.mock
def test_list_members() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/pools/p-1/members").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "m-1"}], "message": "ok"}
        )
    )
    assert _client().list_members("lb-1", "p-1") == [{"id": "m-1"}]


@respx.mock
def test_create_member() -> None:
    route = respx.post(f"{BASE}{PREFIX}/lb-1/pools/p-1/members").mock(
        return_value=httpx.Response(201, json={"id": "m-1"})
    )
    _client().create_member(
        "lb-1", "p-1", {"address": "10.0.0.5", "protocol_port": 80, "weight": 1}
    )
    body = route.calls.last.request.read().decode()
    assert "10.0.0.5" in body


@respx.mock
def test_get_member() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/pools/p-1/members/m-1").mock(
        return_value=httpx.Response(200, json={"id": "m-1"})
    )
    _client().get_member("lb-1", "p-1", "m-1")


@respx.mock
def test_delete_member() -> None:
    respx.delete(f"{BASE}{PREFIX}/lb-1/pools/p-1/members/m-1").mock(
        return_value=httpx.Response(200, json={"message": "removed"})
    )
    _client().delete_member("lb-1", "p-1", "m-1")


# ---------- health monitors ----------


@respx.mock
def test_create_health_monitor() -> None:
    route = respx.post(f"{BASE}{PREFIX}/lb-1/pools/p-1/healthmonitor").mock(
        return_value=httpx.Response(201, json={"id": "hm-1"})
    )
    _client().create_health_monitor(
        "lb-1",
        "p-1",
        {"type": "HTTP", "delay": 5, "timeout": 2, "max_retries": 3},
    )
    body = route.calls.last.request.read().decode()
    assert "HTTP" in body and "max_retries" in body


@respx.mock
def test_get_health_monitor() -> None:
    respx.get(f"{BASE}{PREFIX}/lb-1/pools/p-1/healthmonitor/hm-1").mock(
        return_value=httpx.Response(200, json={"id": "hm-1"})
    )
    _client().get_health_monitor("lb-1", "p-1", "hm-1")


@respx.mock
def test_delete_health_monitor() -> None:
    respx.delete(f"{BASE}{PREFIX}/lb-1/pools/p-1/healthmonitor/hm-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    _client().delete_health_monitor("lb-1", "p-1", "hm-1")
