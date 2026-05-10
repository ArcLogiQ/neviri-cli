"""Typed wrapper around BaseClient for the backend's compute endpoints.

Maps to ``/api/v1/compute/*`` per ADR 0001:
- servers (list/create/get/delete + action/resize/console)
- flavors (list)
- images (list)

Hand-written - codegen is deferred to Phase 2 per the project decisions
captured in this conversation.
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient

PREFIX = "/api/v1/compute"


class ComputeClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- servers ------------------------------------------------------

    def list_servers(
        self,
        *,
        status: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if name:
            params["name"] = name
        result = self._base.get(f"{PREFIX}/servers", params=params or None)
        return result if isinstance(result, list) else []

    def create_server(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/servers", json=data)
        return result if isinstance(result, dict) else {}

    def get_server(self, server_id: str) -> dict[str, Any]:
        result = self._base.get(f"{PREFIX}/servers/{server_id}")
        return result if isinstance(result, dict) else {}

    def delete_server(self, server_id: str, *, force: bool = False) -> dict[str, Any]:
        params = {"force": "true"} if force else None
        result = self._base.delete(f"{PREFIX}/servers/{server_id}", params=params)
        return result if isinstance(result, dict) else {}

    def server_action(
        self,
        server_id: str,
        action: str,
        *,
        reboot_type: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"action": action}
        if reboot_type is not None:
            body["reboot_type"] = reboot_type
        result = self._base.post(f"{PREFIX}/servers/{server_id}/action", json=body)
        return result if isinstance(result, dict) else {}

    def resize_server(self, server_id: str, flavor_id: str) -> dict[str, Any]:
        result = self._base.post(
            f"{PREFIX}/servers/{server_id}/resize",
            json={"flavor_id": flavor_id},
        )
        return result if isinstance(result, dict) else {}

    def confirm_resize(self, server_id: str) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/servers/{server_id}/resize/confirm")
        return result if isinstance(result, dict) else {}

    def revert_resize(self, server_id: str) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/servers/{server_id}/resize/revert")
        return result if isinstance(result, dict) else {}

    def get_console(self, server_id: str, *, console_type: str = "novnc") -> dict[str, Any]:
        result = self._base.get(
            f"{PREFIX}/servers/{server_id}/console",
            params={"console_type": console_type},
        )
        return result if isinstance(result, dict) else {}

    # --- flavors / images ---------------------------------------------

    def list_flavors(self) -> list[dict[str, Any]]:
        result = self._base.get(f"{PREFIX}/flavors")
        return result if isinstance(result, list) else []

    def list_images(self) -> list[dict[str, Any]]:
        result = self._base.get(f"{PREFIX}/images")
        return result if isinstance(result, list) else []
