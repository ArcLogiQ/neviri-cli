"""Typed wrapper for `/api/v1/block-storage/*` (volumes + snapshots).

Note: the backend does NOT expose a volume resize endpoint, so this client
omits it intentionally. If/when the backend adds it, mirror the shape of
``ComputeClient.resize_server``.
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient

PREFIX = "/api/v1/block-storage"


class BlockStorageClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- volumes -----------------------------------------------------

    def list_volumes(
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
        result = self._base.get(f"{PREFIX}/volumes", params=params or None)
        return result if isinstance(result, list) else []

    def create_volume(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/volumes", json=data)
        return result if isinstance(result, dict) else {}

    def get_volume(self, volume_id: str) -> dict[str, Any]:
        result = self._base.get(f"{PREFIX}/volumes/{volume_id}")
        return result if isinstance(result, dict) else {}

    def delete_volume(self, volume_id: str) -> dict[str, Any]:
        result = self._base.delete(f"{PREFIX}/volumes/{volume_id}")
        return result if isinstance(result, dict) else {}

    def attach_volume(
        self, volume_id: str, server_id: str, *, device: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"server_id": server_id}
        if device is not None:
            body["device"] = device
        result = self._base.post(f"{PREFIX}/volumes/{volume_id}/attach", json=body)
        return result if isinstance(result, dict) else {}

    def detach_volume(self, volume_id: str, server_id: str) -> dict[str, Any]:
        result = self._base.post(
            f"{PREFIX}/volumes/{volume_id}/detach",
            json={"server_id": server_id},
        )
        return result if isinstance(result, dict) else {}

    # --- snapshots ---------------------------------------------------

    def list_snapshots(self, *, volume_id: str | None = None) -> list[dict[str, Any]]:
        params = {"volume_id": volume_id} if volume_id else None
        result = self._base.get(f"{PREFIX}/snapshots", params=params)
        return result if isinstance(result, list) else []

    def create_snapshot(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._base.post(f"{PREFIX}/snapshots", json=data)
        return result if isinstance(result, dict) else {}

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        result = self._base.get(f"{PREFIX}/snapshots/{snapshot_id}")
        return result if isinstance(result, dict) else {}

    def delete_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        result = self._base.delete(f"{PREFIX}/snapshots/{snapshot_id}")
        return result if isinstance(result, dict) else {}
