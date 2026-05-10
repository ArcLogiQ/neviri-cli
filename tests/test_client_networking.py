"""Tests for NetworkingClient."""

from __future__ import annotations

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.networking import PREFIX, NetworkingClient

BASE = "https://api.example.test"


def _client() -> NetworkingClient:
    return NetworkingClient(BaseClient(BASE, token="t"))


# ---------- networks ----------


@respx.mock
def test_list_networks() -> None:
    respx.get(f"{BASE}{PREFIX}/networks").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "n1"}], "message": "ok"}
        )
    )
    assert _client().list_networks() == [{"id": "n1"}]


@respx.mock
def test_list_networks_filters() -> None:
    route = respx.get(f"{BASE}{PREFIX}/networks").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_networks(name="public", status="ACTIVE")
    qs = route.calls.last.request.url.query.decode()
    assert "name=public" in qs
    assert "status=ACTIVE" in qs


@respx.mock
def test_create_network() -> None:
    respx.post(f"{BASE}{PREFIX}/networks").mock(
        return_value=httpx.Response(201, json={"id": "n1", "name": "my-net"})
    )
    assert _client().create_network({"name": "my-net"}) == {"id": "n1", "name": "my-net"}


@respx.mock
def test_get_network() -> None:
    respx.get(f"{BASE}{PREFIX}/networks/n1").mock(
        return_value=httpx.Response(200, json={"id": "n1"})
    )
    assert _client().get_network("n1") == {"id": "n1"}


@respx.mock
def test_delete_network() -> None:
    respx.delete(f"{BASE}{PREFIX}/networks/n1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert _client().delete_network("n1") == {"message": "deleted"}


# ---------- subnets ----------


@respx.mock
def test_list_subnets_filters() -> None:
    route = respx.get(f"{BASE}{PREFIX}/subnets").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_subnets(network_id="n1", name="web")
    qs = route.calls.last.request.url.query.decode()
    assert "network_id=n1" in qs
    assert "name=web" in qs


@respx.mock
def test_create_subnet() -> None:
    respx.post(f"{BASE}{PREFIX}/subnets").mock(return_value=httpx.Response(201, json={"id": "s1"}))
    body = {"name": "web", "network_id": "n1", "cidr": "10.0.0.0/24", "ip_version": 4}
    assert _client().create_subnet(body) == {"id": "s1"}


@respx.mock
def test_get_subnet() -> None:
    respx.get(f"{BASE}{PREFIX}/subnets/s1").mock(
        return_value=httpx.Response(200, json={"id": "s1"})
    )
    assert _client().get_subnet("s1") == {"id": "s1"}


@respx.mock
def test_delete_subnet() -> None:
    respx.delete(f"{BASE}{PREFIX}/subnets/s1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert _client().delete_subnet("s1") == {"message": "deleted"}


# ---------- floating IPs ----------


@respx.mock
def test_list_floating_ips() -> None:
    respx.get(f"{BASE}{PREFIX}/floating-ips").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": "fip"}], "message": "ok"}
        )
    )
    assert _client().list_floating_ips() == [{"id": "fip"}]


@respx.mock
def test_list_floating_ips_with_status() -> None:
    route = respx.get(f"{BASE}{PREFIX}/floating-ips").mock(
        return_value=httpx.Response(200, json={"status": True, "data": [], "message": "ok"})
    )
    _client().list_floating_ips(status="ACTIVE")
    assert b"status=ACTIVE" in route.calls.last.request.url.query


@respx.mock
def test_allocate_floating_ip() -> None:
    route = respx.post(f"{BASE}{PREFIX}/floating-ips").mock(
        return_value=httpx.Response(201, json={"id": "fip", "floating_ip_address": "1.2.3.4"})
    )
    _client().allocate_floating_ip({"floating_network_id": "ext-net"})
    body = route.calls.last.request.read().decode()
    assert "ext-net" in body


@respx.mock
def test_get_floating_ip() -> None:
    respx.get(f"{BASE}{PREFIX}/floating-ips/fip").mock(
        return_value=httpx.Response(200, json={"id": "fip"})
    )
    assert _client().get_floating_ip("fip") == {"id": "fip"}


@respx.mock
def test_release_floating_ip() -> None:
    respx.delete(f"{BASE}{PREFIX}/floating-ips/fip").mock(
        return_value=httpx.Response(200, json={"message": "released"})
    )
    assert _client().release_floating_ip("fip") == {"message": "released"}


@respx.mock
def test_associate_floating_ip() -> None:
    route = respx.put(f"{BASE}{PREFIX}/floating-ips/fip/associate").mock(
        return_value=httpx.Response(200, json={"id": "fip", "port_id": "p1"})
    )
    _client().associate_floating_ip("fip", "p1")
    body = route.calls.last.request.read().decode()
    assert "p1" in body


@respx.mock
def test_disassociate_floating_ip() -> None:
    respx.put(f"{BASE}{PREFIX}/floating-ips/fip/disassociate").mock(
        return_value=httpx.Response(200, json={"id": "fip", "port_id": None})
    )
    assert _client().disassociate_floating_ip("fip") == {"id": "fip", "port_id": None}
