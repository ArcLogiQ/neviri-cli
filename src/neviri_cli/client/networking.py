"""Typed wrapper for `/api/v1/network/*` — networks, subnets, floating IPs.

The backend exposes routers as well (`/network/routers`) but those aren't on
the Phase 1 CLI roadmap; add when needed.
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient

PREFIX = "/api/v1/network"


class NetworkingClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- networks ----------------------------------------------------

    def list_networks(
        self,
        *,
        name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if name:
            params["name"] = name
        if status:
            params["status"] = status
        result = self._base.get(f"{PREFIX}/networks", params=params or None)
        return result if isinstance(result, list) else []

    def create_network(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/networks", json=data)
        return result if isinstance(result, dict) else {}

    def get_network(self, network_id: str) -> dict[str, Any]:
        result = self._base.get(f"{PREFIX}/networks/{network_id}")
        return result if isinstance(result, dict) else {}

    def delete_network(self, network_id: str) -> dict[str, Any]:
        result = self._base.delete(f"{PREFIX}/networks/{network_id}")
        return result if isinstance(result, dict) else {}

    # --- subnets -----------------------------------------------------

    def list_subnets(
        self,
        *,
        network_id: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if network_id:
            params["network_id"] = network_id
        if name:
            params["name"] = name
        result = self._base.get(f"{PREFIX}/subnets", params=params or None)
        return result if isinstance(result, list) else []

    def create_subnet(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/subnets", json=data)
        return result if isinstance(result, dict) else {}

    def get_subnet(self, subnet_id: str) -> dict[str, Any]:
        result = self._base.get(f"{PREFIX}/subnets/{subnet_id}")
        return result if isinstance(result, dict) else {}

    def delete_subnet(self, subnet_id: str) -> dict[str, Any]:
        result = self._base.delete(f"{PREFIX}/subnets/{subnet_id}")
        return result if isinstance(result, dict) else {}

    # --- floating IPs -----------------------------------------------

    def list_floating_ips(self, *, status: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status} if status else None
        result = self._base.get(f"{PREFIX}/floating-ips", params=params)
        return result if isinstance(result, list) else []

    def allocate_floating_ip(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/floating-ips", json=data)
        return result if isinstance(result, dict) else {}

    def get_floating_ip(self, floating_ip_id: str) -> dict[str, Any]:
        result = self._base.get(f"{PREFIX}/floating-ips/{floating_ip_id}")
        return result if isinstance(result, dict) else {}

    def release_floating_ip(self, floating_ip_id: str) -> dict[str, Any]:
        result = self._base.delete(f"{PREFIX}/floating-ips/{floating_ip_id}")
        return result if isinstance(result, dict) else {}

    def associate_floating_ip(self, floating_ip_id: str, port_id: str) -> dict[str, Any]:
        result = self._base.put(
            f"{PREFIX}/floating-ips/{floating_ip_id}/associate",
            json={"port_id": port_id},
        )
        return result if isinstance(result, dict) else {}

    def disassociate_floating_ip(self, floating_ip_id: str) -> dict[str, Any]:
        result = self._base.put(f"{PREFIX}/floating-ips/{floating_ip_id}/disassociate")
        return result if isinstance(result, dict) else {}
