"""Tests for the three engine database clients."""

from __future__ import annotations

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.database import MongoClient, MysqlClient, PostgresClient

BASE = "https://api.example.test"


# ---------- MysqlClient ----------


@respx.mock
def test_mysql_list() -> None:
    respx.get(f"{BASE}/api/v1/mysql/all-mysql").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 1}], "message": "ok"}
        )
    )
    assert MysqlClient(BaseClient(BASE, token="t")).list_databases() == [{"id": 1}]


@respx.mock
def test_mysql_create_posts_body() -> None:
    route = respx.post(f"{BASE}/api/v1/mysql/create-mysql").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    MysqlClient(BaseClient(BASE, token="t")).create_database(
        {"name": "db", "flavor": "SMALL", "mysql_user": "u", "mysql_pass": "p"}
    )
    body = route.calls.last.request.read().decode()
    assert "mysql_user" in body and "SMALL" in body


@respx.mock
def test_mysql_delete() -> None:
    respx.delete(f"{BASE}/api/v1/mysql/delete-mysql/7").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    assert MysqlClient(BaseClient(BASE, token="t")).delete_database(7) == {"message": "deleted"}


@respx.mock
def test_mysql_scale_puts_body() -> None:
    route = respx.put(f"{BASE}/api/v1/mysql/scale-mysql/7").mock(
        return_value=httpx.Response(200, json={"message": "scaling"})
    )
    MysqlClient(BaseClient(BASE, token="t")).scale_database(7, {"flavor": "BIG"})
    body = route.calls.last.request.read().decode()
    assert "BIG" in body


@respx.mock
def test_mysql_status() -> None:
    respx.get(f"{BASE}/api/v1/mysql/status-mysql/7").mock(
        return_value=httpx.Response(200, json={"id": 7, "status": "ACTIVE"})
    )
    assert MysqlClient(BaseClient(BASE, token="t")).get_status(7)["status"] == "ACTIVE"


@respx.mock
def test_mysql_flavors() -> None:
    respx.get(f"{BASE}/api/v1/mysql/flavors").mock(
        return_value=httpx.Response(200, json={"flavors": [{"name": "SMALL", "cpu": 1}]})
    )
    result = MysqlClient(BaseClient(BASE, token="t")).list_flavors()
    assert "flavors" in result


# ---------- PostgresClient ----------


@respx.mock
def test_pg_list() -> None:
    respx.get(f"{BASE}/api/v1/postgres/all-postgres").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 2}], "message": "ok"}
        )
    )
    assert PostgresClient(BaseClient(BASE, token="t")).list_databases() == [{"id": 2}]


@respx.mock
def test_pg_create() -> None:
    respx.post(f"{BASE}/api/v1/postgres/create-postgres").mock(
        return_value=httpx.Response(201, json={"id": 2})
    )
    assert PostgresClient(BaseClient(BASE, token="t")).create_database({"name": "db"}) == {"id": 2}


@respx.mock
def test_pg_delete() -> None:
    respx.delete(f"{BASE}/api/v1/postgres/delete-postgres/2").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    PostgresClient(BaseClient(BASE, token="t")).delete_database(2)


@respx.mock
def test_pg_scale() -> None:
    respx.put(f"{BASE}/api/v1/postgres/scale-postgres/2").mock(
        return_value=httpx.Response(200, json={"message": "scaling"})
    )
    PostgresClient(BaseClient(BASE, token="t")).scale_database(2, {"flavor": "BIG"})


@respx.mock
def test_pg_status() -> None:
    respx.get(f"{BASE}/api/v1/postgres/status-postgres/2").mock(
        return_value=httpx.Response(200, json={"status": "ACTIVE"})
    )
    PostgresClient(BaseClient(BASE, token="t")).get_status(2)


@respx.mock
def test_pg_flavors() -> None:
    respx.get(f"{BASE}/api/v1/postgres/flavors").mock(
        return_value=httpx.Response(200, json={"flavors": []})
    )
    PostgresClient(BaseClient(BASE, token="t")).list_flavors()


# ---------- MongoClient ----------


@respx.mock
def test_mongo_list_uses_type_filter() -> None:
    route = respx.get(f"{BASE}/api/v1/database/all-databases").mock(
        return_value=httpx.Response(
            200, json={"status": True, "data": [{"id": 3}], "message": "ok"}
        )
    )
    MongoClient(BaseClient(BASE, token="t")).list_databases()
    assert b"type=mongodb" in route.calls.last.request.url.query


@respx.mock
def test_mongo_create() -> None:
    respx.post(f"{BASE}/api/v1/database/create-deployment").mock(
        return_value=httpx.Response(201, json={"id": 3})
    )
    assert MongoClient(BaseClient(BASE, token="t")).create_database({"name": "m"}) == {"id": 3}


@respx.mock
def test_mongo_delete() -> None:
    respx.delete(f"{BASE}/api/v1/database/delete-database/3").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    MongoClient(BaseClient(BASE, token="t")).delete_database(3)


@respx.mock
def test_mongo_scale() -> None:
    respx.put(f"{BASE}/api/v1/database/scale-database/3").mock(
        return_value=httpx.Response(200, json={"message": "scaling"})
    )
    MongoClient(BaseClient(BASE, token="t")).scale_database(3, {"flavor": "M20", "type": "mongodb"})


@respx.mock
def test_mongo_status() -> None:
    respx.get(f"{BASE}/api/v1/database/status/3").mock(
        return_value=httpx.Response(200, json={"status": "ACTIVE"})
    )
    MongoClient(BaseClient(BASE, token="t")).get_status(3)


# ---------- defensive ----------


@respx.mock
def test_list_returns_empty_when_response_is_dict() -> None:
    respx.get(f"{BASE}/api/v1/mysql/all-mysql").mock(
        return_value=httpx.Response(200, json={"status": False})
    )
    assert MysqlClient(BaseClient(BASE, token="t")).list_databases() == []
