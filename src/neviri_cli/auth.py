"""Auth helpers shared by the auth subcommand and per-call client construction.

Phase 1 policy (deliberately simple):

- Login = POST ``/api/v1/user/login``, get a 24h JWT, drop the ``refreshToken``
  field on the floor. No transparent refresh.
- API tokens (``nvr_*``) are accepted: stored verbatim and passed through.
- Identity for ``whoami`` comes from the JWT payload (decoded without
  verification - that's a display, not a trust decision) cached into
  ``~/.neviri/config.toml`` at login time.

Refresh-token logic and ``neviri auth token create/list/delete`` are Phase 2.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from neviri_cli.client.base import BaseClient
from neviri_cli.credentials import get_token_store
from neviri_cli.exceptions import AuthError

ENV_TOKEN = "NEVIRI_API_TOKEN"
API_TOKEN_PREFIX = "nvr_"


def get_active_token(profile: str) -> str | None:
    """Resolve the token to use for a request.

    Priority:
        1. ``$NEVIRI_API_TOKEN`` (per-invocation override; CI-friendly)
        2. The keyring/file store under the active profile
        3. ``None`` - caller must handle as not-logged-in
    """
    env = os.environ.get(ENV_TOKEN)
    if env:
        return env
    return get_token_store().get(profile)


def store_token(profile: str, token: str) -> None:
    get_token_store().set(profile, token)


def clear_token(profile: str) -> None:
    get_token_store().delete(profile)


def is_api_token(token: str) -> bool:
    return token.startswith(API_TOKEN_PREFIX)


def login_with_password(auth_url: str, email: str, password: str) -> dict[str, Any]:
    """Hit the auth service and return the parsed login response.

    Raises :class:`AuthError` on bad credentials, :class:`NetworkError` on
    transport failure, etc. (mapped by ``BaseClient``).
    """
    with BaseClient(auth_url) as client:
        response = client.post(
            "/api/v1/user/login",
            json={"email": email, "password": password},
        )
    if not isinstance(response, dict) or not response.get("status"):
        message = "login failed"
        if isinstance(response, dict):
            message = str(response.get("message", message))
        raise AuthError(message)
    return response


def decode_jwt_payload_unsafe(token: str) -> dict[str, Any] | None:
    """Best-effort JWT payload decode for *display only*.

    Does NOT verify the signature. Used for ``whoami`` output and to extract
    ``accountId`` for the identity cache. Never trust the returned values for
    authorization decisions - the backend is the only place that verifies.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Re-add base64 padding that JWT strips.
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        result = json.loads(decoded)
        return result if isinstance(result, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None
