"""Typed wrappers for ``/api/v1/apps/*`` and ``/api/v1/deployments/*``.

These two routers are tightly coupled - apps own deployments, deployments own
build/deploy/service/ingress stages - so one client covers both.

Backend gaps the CLI surfaces honestly (no backend changes per session rule):

* No ``app logs`` endpoint -> CLI omits the command.
* No ``app restart`` endpoint -> CLI omits the command.
* No deployment ``rollback`` endpoint -> CLI omits the command.
* No log-streaming endpoint -> ``neviri deploy logs -f`` polls
  ``GET /deployments/{id}`` and prints ``build_log`` deltas.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any

from neviri_cli.client.base import BaseClient
from neviri_cli.client.object_storage import ProgressCallback, _CallbackReader

APPS_PREFIX = "/api/v1/apps"
DEPLOYMENTS_PREFIX = "/api/v1/deployments"


def _as_list(x: Any) -> list[dict[str, Any]]:
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class DeploymentClient:
    """Covers app lifecycle, env vars, ZIP upload, and deployment stages."""

    def __init__(self, base: BaseClient) -> None:
        self._base = base

    # --- apps -------------------------------------------------------

    def list_apps(self) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{APPS_PREFIX}/"))

    def create_app(self, name: str) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{APPS_PREFIX}/", json={"name": name}))

    def get_app(self, app_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{APPS_PREFIX}/{app_id}"))

    def delete_app(self, app_id: int) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{APPS_PREFIX}/{app_id}"))

    def list_deployments(self, app_id: int) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{APPS_PREFIX}/{app_id}/deployments"))

    def upload_zip(
        self,
        app_id: int,
        file_path: Path,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Upload a ZIP and create a new deployment.

        Uses the same _CallbackReader trick as object-storage upload so the
        CLI can show a real byte-level progress bar.
        """
        with file_path.open("rb") as raw:
            fp: IO[bytes] = (
                _CallbackReader(raw, on_progress) if on_progress else raw  # type: ignore[assignment]
            )
            files = {"file": (file_path.name, fp, "application/zip")}
            return _as_dict(self._base.post(f"{APPS_PREFIX}/{app_id}/upload", files=files))

    # --- env vars ---------------------------------------------------

    def list_env_variables(self, app_id: int) -> list[dict[str, Any]]:
        return _as_list(self._base.get(f"{APPS_PREFIX}/{app_id}/env"))

    def add_env_variable(self, app_id: int, key: str, value: str) -> dict[str, Any]:
        return _as_dict(
            self._base.post(f"{APPS_PREFIX}/{app_id}/env", json={"key": key, "value": value})
        )

    def delete_env_variable(self, app_id: int, env_id: int) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{APPS_PREFIX}/{app_id}/env/{env_id}"))

    # --- deployment stages -----------------------------------------

    def get_deployment(self, deployment_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{DEPLOYMENTS_PREFIX}/{deployment_id}"))

    def get_manifests(self, deployment_id: int) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{DEPLOYMENTS_PREFIX}/{deployment_id}/manifests"))

    def trigger_build(self, deployment_id: int) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{DEPLOYMENTS_PREFIX}/{deployment_id}/build"))

    def trigger_deploy(self, deployment_id: int) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{DEPLOYMENTS_PREFIX}/{deployment_id}/deploy"))

    def trigger_service(self, deployment_id: int) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{DEPLOYMENTS_PREFIX}/{deployment_id}/service"))

    def trigger_ingress(self, deployment_id: int) -> dict[str, Any]:
        return _as_dict(self._base.post(f"{DEPLOYMENTS_PREFIX}/{deployment_id}/ingress"))
