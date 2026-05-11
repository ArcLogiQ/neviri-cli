"""Typed wrapper for backup + restore endpoints.

The backend exposes one universal backup router at ``/api/v1/backup/*`` that
auto-detects the database type from the cluster name. A separate restore
router lives at ``/api/v1/restore/*``.

For the CLI, both engines (MySQL, Postgres) and MongoDB hit the same backup
endpoints — we pass ``database_type`` through and let the backend dispatch.
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient

BACKUP_PREFIX = "/api/v1/backup"
RESTORE_PREFIX = "/api/v1/restore"


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class BackupClient:
    """Cluster-agnostic backup orchestration."""

    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- backups ----------------------------------------------------

    def create_backup(self, *, cluster_name: str, database_type: str) -> dict[str, Any]:
        return _as_dict(
            self._base.post(
                f"{BACKUP_PREFIX}/create",
                json={"cluster_name": cluster_name, "database_type": database_type},
            )
        )

    def list_backups(self, *, cluster_name: str | None = None) -> dict[str, Any]:
        # Returns {"status": True, "data": {"backups": [...]}} on the wire.
        # BaseClient.unwrap leaves dict payloads alone, so callers see the
        # raw envelope and pull `.data.backups`.
        params = {"clusterName": cluster_name} if cluster_name else None
        return _as_dict(self._base.get(f"{BACKUP_PREFIX}/list", params=params))

    def get_backup(self, backup_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{BACKUP_PREFIX}/details/{backup_id}"))

    def delete_backup(self, backup_id: int) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{BACKUP_PREFIX}/delete/{backup_id}"))

    def download_backup(self, backup_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{BACKUP_PREFIX}/download/{backup_id}"))

    # --- restore ----------------------------------------------------

    def initiate_restore(
        self,
        *,
        backup_id: int,
        target_cluster_name: str,
        restore_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "backup_id": backup_id,
            "target_cluster_name": target_cluster_name,
        }
        if restore_options is not None:
            body["restore_options"] = restore_options
        return _as_dict(self._base.post(f"{RESTORE_PREFIX}/initiate", json=body))

    def get_restore_status(self, backup_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{RESTORE_PREFIX}/status/{backup_id}"))

    def cancel_restore(self, backup_id: int) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{RESTORE_PREFIX}/cancel/{backup_id}"))
