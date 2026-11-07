"""Fixed IAM STOP/status operations with explicit idempotency and safe output."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from neviri_cli.client.base import BaseClient
from neviri_cli.config import ProfileConfig
from neviri_cli.exceptions import NetworkError, NeviriCLIError, ServerError, UserError
from neviri_cli.iam import require_iam_profile, resolve_iam_token, validate_iam_origin

STATES = {
    "prepared",
    "submitting",
    "accepted",
    "confirmed",
    "unknown",
    "failed",
    "blocked",
    "needs_review",
}


def canonical_uuid(value: object) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as exc:
        raise UserError("An exact canonical UUID is required") from exc
    return value


def validate_key(value: str | None) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", value):
        raise UserError("IAM STOP requires --idempotency-key (8-128 ASCII letters/digits/._:-)")
    return value


def recovery_metadata(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    try:
        operation_id = canonical_uuid(value.get("operation_id"))
    except UserError:
        return {}
    result = {"operation_id": operation_id}
    if isinstance(value.get("operation_status"), str) and value["operation_status"] in STATES:
        result["operation_status"] = value["operation_status"]
    return result


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 64 or "T" not in value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def operation_view(value: Any) -> dict[str, Any]:
    try:
        if not isinstance(value, dict):
            raise ValueError()
        metadata = recovery_metadata(value)
        server_id = canonical_uuid(value.get("server_id"))
        if (
            "operation_status" not in metadata
            or value.get("action") != "stop"
            or type(value.get("revision")) is not int
            or value["revision"] < 1
            or not _timestamp(value.get("created_at"))
            or (value.get("confirmed_at") is not None and not _timestamp(value["confirmed_at"]))
        ):
            raise ValueError()
        for field in ("observed_status", "failure_code"):
            if value.get(field) is not None and (
                not isinstance(value[field], str)
                or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value[field])
            ):
                raise ValueError()
        return {
            "message": "Server stop operation",
            **metadata,
            "server_id": server_id,
            "revision": value["revision"],
            "action": "stop",
            "observed_status": value.get("observed_status"),
            "failure_code": value.get("failure_code"),
            "created_at": value["created_at"],
            "confirmed_at": value.get("confirmed_at"),
        }
    except (ValueError, UserError) as exc:
        raise ServerError("Service returned an invalid operation response") from exc


class IAMOperationError(NeviriCLIError):
    def __init__(self, status: int, metadata: dict[str, str]) -> None:
        self.exit_code = 3 if status in (401, 403) else 5 if status >= 500 else 2
        self.operation_id = metadata.get("operation_id")
        self.operation_status = metadata.get("operation_status")
        message = (
            "IAM operation request was rejected"
            if status < 500
            else "IAM operation outcome requires verification"
        )
        if self.operation_id:
            state = f" ({self.operation_status})" if self.operation_status else ""
            message += (
                f". Operation: {self.operation_id}{state}; "
                f"use `iam operation-status {self.operation_id}`"
            )
        super().__init__(message)


class _OperationClient(BaseClient):
    """No upstream error text, headers or validation echoes enter new IAM output."""

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            return super().request(method, path, **kwargs)
        except NetworkError:
            raise NetworkError(
                "IAM operation request failed; reuse the same idempotency key"
            ) from None

    def _raise_for_response(self, response: httpx.Response) -> None:
        try:
            metadata = recovery_metadata(response.json())
        except (ValueError, RecursionError):
            metadata = {}
        raise IAMOperationError(response.status_code, metadata)

    def _parse_body(self, response: httpx.Response) -> Any:
        try:
            return operation_view(response.json())
        except (ValueError, RecursionError):
            raise ServerError("Service returned an invalid operation response") from None

    def _debug_response(self, response: httpx.Response) -> None:
        try:
            metadata = recovery_metadata(response.json())
        except (ValueError, RecursionError):
            metadata = {}
        self._debug_emit(f"<-- {response.status_code}", headers={}, body=metadata)


def _client(name: str, profile: ProfileConfig, *, timeout: float, debug: bool) -> _OperationClient:
    require_iam_profile(profile)
    origin = validate_iam_origin(profile.api_url)
    token = resolve_iam_token(name, profile, debug=debug)
    return _OperationClient(origin, token=token, timeout=timeout, max_retries=0, debug=debug)


def stop_server(
    name: str, profile: ProfileConfig, server_id: str, key: str | None, *, debug: bool = False
) -> dict[str, Any]:
    server_id, key = canonical_uuid(server_id), validate_key(key)
    with _client(name, profile, timeout=65.0, debug=debug) as client:
        result: dict[str, Any] = client.post(
            f"/api/v1/compute/servers/{server_id}/action",
            json={"action": "stop"},
            headers={"Idempotency-Key": key},
        )
    if result["server_id"] != server_id:
        raise ServerError("Operation does not match the requested server")
    return result


def get_operation(
    name: str, profile: ProfileConfig, operation_id: str, *, debug: bool = False
) -> dict[str, Any]:
    operation_id = canonical_uuid(operation_id)
    with _client(name, profile, timeout=10.0, debug=debug) as client:
        result: dict[str, Any] = client.get(f"/api/v1/compute/iam/operations/{operation_id}")
    if result["operation_id"] != operation_id:
        raise ServerError("Operation does not match the requested ID")
    return result
