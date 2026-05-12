"""HTTP client base for the Neviri CLI.

Wraps httpx with:
- Bearer token injection (JWT or `nvr_*` API token, both pass through)
- Configurable timeout + bounded retries on transient 5xx / network errors
- request-id capture from the backend's `X-Request-ID` response header
- Backend response-wrapper unwrap for `{status, data, message}` array responses
- Typed CLI exceptions per the exit-code contract (see `exceptions.py`)
- Optional `--debug` request/response trace to stderr, with credentials
  redacted via :mod:`neviri_cli.utils.redact`

The CLI is a pure HTTP client by architectural rule (proposal section 4.1) -
no business logic, no OpenStack SDK calls, no DB connections.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx

from neviri_cli.exceptions import (
    AuthError,
    NetworkError,
    NeviriCLIError,
    ServerError,
    UserError,
)
from neviri_cli.utils.redact import redact


def unwrap_response(payload: Any) -> Any:
    """Strip the `{status, data, message}` envelope used by the backend's
    response-wrapper middleware on array endpoints.

    Pass-through for everything else, so dict responses (which the middleware
    leaves untouched) stay untouched here too.
    """
    if (
        isinstance(payload, dict)
        and set(payload.keys()) >= {"status", "data"}
        and isinstance(payload["data"], list)
    ):
        return payload["data"]
    return payload


def _is_retryable(status: int) -> bool:
    return status in (502, 503, 504) or status == 429


class BaseClient:
    """Synchronous HTTP client over httpx."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.25,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
        debug: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._max_retries = max(0, max_retries)
        self._retry_backoff = retry_backoff
        self._last_request_id: str | None = None
        self._debug = debug

        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": user_agent or "neviri-cli",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    # --- public ---------------------------------------------------------

    @property
    def last_request_id(self) -> str | None:
        return self._last_request_id

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BaseClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        attempt = 0
        last_response: httpx.Response | None = None
        if self._debug:
            self._debug_request(method, path, kwargs)
        while True:
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    time.sleep(self._retry_backoff * attempt)
                    continue
                raise NetworkError(f"request timed out: {exc}") from exc
            except httpx.TransportError as exc:
                # connect errors, DNS, TLS, etc.
                if attempt < self._max_retries:
                    attempt += 1
                    time.sleep(self._retry_backoff * attempt)
                    continue
                raise NetworkError(f"network error: {exc}") from exc

            self._last_request_id = response.headers.get("x-request-id")

            if self._debug:
                self._debug_response(response)

            if response.status_code < 400:
                return self._parse_body(response)

            if _is_retryable(response.status_code) and attempt < self._max_retries:
                attempt += 1
                last_response = response
                time.sleep(self._retry_backoff * attempt)
                continue

            self._raise_for_response(response)
            # Defensive: _raise_for_response always raises.
            raise AssertionError("unreachable")  # pragma: no cover

        del last_response  # pragma: no cover

    # --- internals ------------------------------------------------------

    def _parse_body(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        ctype = response.headers.get("content-type", "")
        if "application/json" not in ctype:
            return response.text
        try:
            return unwrap_response(response.json())
        except ValueError as exc:
            raise NeviriCLIError(f"server returned invalid JSON: {exc}") from exc

    def _raise_for_response(self, response: httpx.Response) -> None:
        request_id = response.headers.get("x-request-id")
        message = self._extract_message(response)
        status = response.status_code

        if status in (401,):
            raise AuthError(message or "authentication required", request_id=request_id)
        if status in (403,):
            raise AuthError(message or "permission denied", request_id=request_id)
        if 400 <= status < 500:
            raise UserError(message or f"bad request ({status})", request_id=request_id)
        if 500 <= status < 600:
            raise ServerError(message or f"server error ({status})", request_id=request_id)
        # Any other unexpected status code.
        raise NeviriCLIError(  # pragma: no cover
            message or f"unexpected response ({status})", request_id=request_id
        )

    @staticmethod
    def _extract_message(response: httpx.Response) -> str | None:
        try:
            body = response.json()
        except ValueError:
            return None
        if isinstance(body, dict):
            for key in ("message", "detail", "error"):
                value = body.get(key)
                if isinstance(value, str):
                    return value
        return None

    # --- debug logging --------------------------------------------------

    def _debug_request(self, method: str, path: str, kwargs: dict[str, Any]) -> None:
        """Dump the outbound request to stderr with credentials redacted.

        Output is human-readable, not machine-parseable. The goal is to make
        diagnosing CLI/backend mismatches obvious without leaking secrets.
        """
        url = path if path.startswith("http") else f"{self._base_url}{path}"
        headers = self._merged_headers(kwargs.get("headers"))
        body = kwargs.get("json") if "json" in kwargs else kwargs.get("data")
        self._debug_emit(f"--> {method.upper()} {url}", headers=headers, body=body)

    def _debug_response(self, response: httpx.Response) -> None:
        """Dump the inbound response to stderr with credentials redacted."""
        body: Any
        try:
            body = response.json()
        except ValueError:
            # Truncate non-JSON bodies to keep terminals readable.
            text = response.text
            body = text if len(text) <= 500 else f"{text[:500]}... [truncated]"
        self._debug_emit(
            f"<-- {response.status_code} {response.reason_phrase}",
            headers=dict(response.headers),
            body=body,
        )

    def _merged_headers(self, override: Any) -> dict[str, str]:
        merged: dict[str, str] = {str(k): str(v) for k, v in self._client.headers.items()}
        if isinstance(override, dict):
            for k, v in override.items():
                merged[str(k)] = str(v)
        return merged

    @staticmethod
    def _debug_emit(line: str, *, headers: dict[str, str], body: Any) -> None:
        print(line, file=sys.stderr)
        for k, v in redact(headers).items():
            print(f"    {k}: {v}", file=sys.stderr)
        if body is None or body == "":
            return
        redacted_body = redact(body)
        try:
            rendered = json.dumps(redacted_body, indent=2, default=str)
        except (TypeError, ValueError):
            rendered = repr(redacted_body)
        for line_out in rendered.splitlines():
            print(f"    {line_out}", file=sys.stderr)
