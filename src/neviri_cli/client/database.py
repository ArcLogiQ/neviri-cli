"""Typed wrappers for the backend's per-engine database routers:

- MongoDB at ``/api/v1/database/*``
- MySQL at ``/api/v1/mysql/*``
- PostgreSQL at ``/api/v1/postgres/*``

The three routers share a *shape* (list/create/delete/scale/status) but their
URL paths and request schemas differ slightly. This module exposes one client
per engine. Each client returns the backend payload as-is (defensive dict
coercion for places the backend lacks ``response_model``).

Many of these endpoints have no ``response_model=`` on the backend, so the
returned dicts are free-form. Phase 2 (Story 14) will tighten this once the
backend OpenAPI spec is cleaned up; for now we treat each response as
``dict[str, Any]`` and let commands pull the fields they want.
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient


def _as_list(x: Any) -> list[dict[str, Any]]:
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class MongoClient:
    """MongoDB cluster management — ``/api/v1/database/*``."""

    PREFIX = "/api/v1/database"

    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def list_databases(self, *, db_type: str = "mongodb") -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{self.PREFIX}/all-databases", params={"type": db_type}))

    def create_database(self, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{self.PREFIX}/create-deployment", json=data))

    def delete_database(self, database_id: int) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{self.PREFIX}/delete-database/{database_id}"))

    def scale_database(self, database_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.put(f"{self.PREFIX}/scale-database/{database_id}", json=data))

    def get_status(self, database_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{self.PREFIX}/status/{database_id}"))


class MysqlClient:
    """MySQL cluster management — ``/api/v1/mysql/*``."""

    PREFIX = "/api/v1/mysql"

    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def list_databases(self) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{self.PREFIX}/all-mysql"))

    def create_database(self, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{self.PREFIX}/create-mysql", json=data))

    def delete_database(self, database_id: int) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{self.PREFIX}/delete-mysql/{database_id}"))

    def scale_database(self, database_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.put(f"{self.PREFIX}/scale-mysql/{database_id}", json=data))

    def get_status(self, database_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{self.PREFIX}/status-mysql/{database_id}"))

    def list_flavors(self) -> dict[str, Any]:
        # Returns {"flavors": [...]}, not a bare list
        return _as_dict(self._base.get(f"{self.PREFIX}/flavors"))


class PostgresClient:
    """PostgreSQL cluster management — ``/api/v1/postgres/*``."""

    PREFIX = "/api/v1/postgres"

    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def list_databases(self) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{self.PREFIX}/all-postgres"))

    def create_database(self, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{self.PREFIX}/create-postgres", json=data))

    def delete_database(self, database_id: int) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{self.PREFIX}/delete-postgres/{database_id}"))

    def scale_database(self, database_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.put(f"{self.PREFIX}/scale-postgres/{database_id}", json=data))

    def get_status(self, database_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{self.PREFIX}/status-postgres/{database_id}"))

    def list_flavors(self) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{self.PREFIX}/flavors"))
