"""Tests for neviri_cli.auth — token resolution + JWT decode + login."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from neviri_cli.auth import (
    ENV_TOKEN,
    clear_token,
    decode_jwt_payload_unsafe,
    get_active_token,
    is_api_token,
    login_with_password,
    store_token,
)
from neviri_cli.exceptions import AuthError


def _make_jwt(payload: dict[str, object]) -> str:
    """Hand-roll a JWT-shaped string. Signature is fake; decode is unsafe-only."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.fake-sig"


# ---------- token resolution ----------


def test_env_var_overrides_keyring(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store_token("default", "from-keyring")
    monkeypatch.setenv(ENV_TOKEN, "from-env")
    assert get_active_token("default") == "from-env"


def test_env_var_used_when_no_stored_token(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_TOKEN, "env-only")
    assert get_active_token("default") == "env-only"


def test_stored_token_used_when_no_env(isolated_home: Path) -> None:
    store_token("default", "from-store")
    assert get_active_token("default") == "from-store"


def test_returns_none_when_neither(isolated_home: Path) -> None:
    assert get_active_token("default") is None


def test_clear_token_removes_from_store(isolated_home: Path) -> None:
    store_token("default", "x")
    clear_token("default")
    assert get_active_token("default") is None


def test_profile_isolation(isolated_home: Path) -> None:
    store_token("default", "a")
    store_token("staging", "b")
    assert get_active_token("default") == "a"
    assert get_active_token("staging") == "b"
    clear_token("default")
    assert get_active_token("default") is None
    assert get_active_token("staging") == "b"


# ---------- is_api_token ----------


def test_is_api_token_recognizes_nvr_prefix() -> None:
    assert is_api_token("nvr_abcd")
    assert not is_api_token("eyJhbGciOiJIUzI1NiJ9.x.y")
    assert not is_api_token("")


# ---------- decode_jwt_payload_unsafe ----------


def test_decode_jwt_payload_returns_claims() -> None:
    token = _make_jwt({"id": 7, "email": "a@b.com", "accountId": 3})
    payload = decode_jwt_payload_unsafe(token)
    assert payload == {"id": 7, "email": "a@b.com", "accountId": 3}


def test_decode_jwt_payload_handles_padding() -> None:
    # short claim that needs padding to base64-decode cleanly
    token = _make_jwt({"a": 1})
    payload = decode_jwt_payload_unsafe(token)
    assert payload == {"a": 1}


def test_decode_jwt_payload_returns_none_on_garbage() -> None:
    assert decode_jwt_payload_unsafe("not-a-jwt") is None
    assert decode_jwt_payload_unsafe("a.b") is None  # only 2 parts
    assert decode_jwt_payload_unsafe("a.@@@@.c") is None  # bad base64


def test_decode_jwt_payload_returns_none_when_payload_not_object() -> None:
    # Payload is a JSON array, not an object
    body = base64.urlsafe_b64encode(b"[1,2,3]").rstrip(b"=").decode()
    token = f"hdr.{body}.sig"
    assert decode_jwt_payload_unsafe(token) is None


# ---------- login_with_password ----------


@respx.mock
def test_login_returns_response_on_success(isolated_home: Path) -> None:
    respx.post("http://localhost:8081/api/v1/user/login").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "token": "jwt-token",
                "refreshToken": "refresh-token",
                "user": {"id": 1, "email": "a@b.com", "name": "A"},
            },
        )
    )
    response = login_with_password("http://localhost:8081", "a@b.com", "pw")
    assert response["token"] == "jwt-token"
    assert response["user"]["email"] == "a@b.com"


@respx.mock
def test_login_raises_auth_error_when_status_false(isolated_home: Path) -> None:
    respx.post("http://localhost:8081/api/v1/user/login").mock(
        return_value=httpx.Response(200, json={"status": False, "message": "bad credentials"})
    )
    with pytest.raises(AuthError) as info:
        login_with_password("http://localhost:8081", "a@b.com", "pw")
    assert "bad credentials" in str(info.value)


@respx.mock
def test_login_raises_auth_error_on_401(isolated_home: Path) -> None:
    respx.post("http://localhost:8081/api/v1/user/login").mock(
        return_value=httpx.Response(401, json={"message": "Incorrect password"})
    )
    with pytest.raises(AuthError):
        login_with_password("http://localhost:8081", "a@b.com", "pw")


# ---------- store_token / clear_token use the active backend ----------


def test_store_token_and_clear_token_round_trip(isolated_home: Path) -> None:
    with patch("neviri_cli.auth.get_token_store") as gts:
        fake_store = type(
            "S",
            (),
            {
                "set": lambda self, p, t: None,
                "delete": lambda self, p: None,
            },
        )()
        gts.return_value = fake_store
        # Just ensure the helpers proxy through without exception.
        store_token("default", "x")
        clear_token("default")
