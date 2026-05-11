"""Typed wrapper for ``/api/v1/load-balancers/*``.

Surface (per backend router):
- load balancers: list / create / get / update / delete
- listeners: list / create / get / update / delete (under lb)
- pools: list / create / get / update / delete (under lb)
- members: list / create / get / update / delete (under pool)
- health monitors: create / get / update / delete (no list; max one per pool)
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient

PREFIX = "/api/v1/load-balancers"


def _as_list(x: Any) -> list[dict[str, Any]]:
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class LoadBalancerClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- load balancers --------------------------------------------

    def list_load_balancers(self, *, name: str | None = None) -> list[dict[str, Any]]:
        params = {"name": name} if name else None
        return _as_list(self._base.get(PREFIX, params=params))

    def create_load_balancer(self, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(PREFIX, json=data))

    def get_load_balancer(self, lb_id: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PREFIX}/{lb_id}"))

    def update_load_balancer(self, lb_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.put(f"{PREFIX}/{lb_id}", json=data))

    def delete_load_balancer(self, lb_id: str, *, cascade: bool = False) -> dict[str, Any]:
        params = {"cascade": "true"} if cascade else None
        return _as_dict(self._base.delete(f"{PREFIX}/{lb_id}", params=params))

    # --- listeners --------------------------------------------------

    def list_listeners(self, lb_id: str) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{PREFIX}/{lb_id}/listeners"))

    def create_listener(self, lb_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{PREFIX}/{lb_id}/listeners", json=data))

    def get_listener(self, lb_id: str, listener_id: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PREFIX}/{lb_id}/listeners/{listener_id}"))

    def delete_listener(self, lb_id: str, listener_id: str) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{PREFIX}/{lb_id}/listeners/{listener_id}"))

    # --- pools ------------------------------------------------------

    def list_pools(self, lb_id: str) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{PREFIX}/{lb_id}/pools"))

    def create_pool(self, lb_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{PREFIX}/{lb_id}/pools", json=data))

    def get_pool(self, lb_id: str, pool_id: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PREFIX}/{lb_id}/pools/{pool_id}"))

    def delete_pool(self, lb_id: str, pool_id: str) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{PREFIX}/{lb_id}/pools/{pool_id}"))

    # --- members ---------------------------------------------------

    def list_members(self, lb_id: str, pool_id: str) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{PREFIX}/{lb_id}/pools/{pool_id}/members"))

    def create_member(self, lb_id: str, pool_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{PREFIX}/{lb_id}/pools/{pool_id}/members", json=data))

    def get_member(self, lb_id: str, pool_id: str, member_id: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PREFIX}/{lb_id}/pools/{pool_id}/members/{member_id}"))

    def delete_member(self, lb_id: str, pool_id: str, member_id: str) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{PREFIX}/{lb_id}/pools/{pool_id}/members/{member_id}"))

    # --- health monitors -------------------------------------------

    def create_health_monitor(
        self, lb_id: str, pool_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return _as_dict(
            self._base.post(f"{PREFIX}/{lb_id}/pools/{pool_id}/healthmonitor", json=data)
        )

    def get_health_monitor(self, lb_id: str, pool_id: str, hm_id: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PREFIX}/{lb_id}/pools/{pool_id}/healthmonitor/{hm_id}"))

    def delete_health_monitor(self, lb_id: str, pool_id: str, hm_id: str) -> dict[str, Any]:
        return _as_dict(
            self._base.delete(f"{PREFIX}/{lb_id}/pools/{pool_id}/healthmonitor/{hm_id}")
        )
