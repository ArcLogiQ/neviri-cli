"""Tests for neviri_cli.client.factory.make_client."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from neviri_cli.auth import store_token
from neviri_cli.client.base import BaseClient
from neviri_cli.client.factory import make_client
from neviri_cli.context import CLIContext
from neviri_cli.exceptions import AuthError


def _ctx(profile: str = "default") -> typer.Context:
    """Hand-build a typer.Context-like object with a CLIContext on .obj.

    The factory only reads ``ctx.obj``; full Context isn't necessary.
    """
    cli_ctx = CLIContext(profile=profile)
    fake = type("FakeCtx", (), {"obj": cli_ctx})()
    return fake  # type: ignore[return-value]


def test_make_client_uses_profile_api_url(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set custom api_url on the default profile
    from neviri_cli.config import CLIConfig, ProfileConfig, save_config

    save_config(
        CLIConfig(
            profiles={
                "default": ProfileConfig(api_url="https://api.example.com"),
            }
        )
    )
    store_token("default", "tok-x")

    client = make_client(_ctx())
    try:
        assert isinstance(client, BaseClient)
        assert client._base_url == "https://api.example.com"  # type: ignore[reportPrivateUsage]
    finally:
        client.close()


def test_make_client_attaches_token_as_bearer(isolated_home: Path) -> None:
    store_token("default", "tok-bearer")
    client = make_client(_ctx())
    try:
        # httpx applies headers from the constructor across requests; verify by
        # peeking at the underlying client's default headers.
        assert client._client.headers["Authorization"] == "Bearer tok-bearer"  # type: ignore[reportPrivateUsage]
    finally:
        client.close()


def test_make_client_uses_env_token_over_store(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_token("default", "from-store")
    monkeypatch.setenv("NEVIRI_API_TOKEN", "from-env")
    client = make_client(_ctx())
    try:
        assert client._client.headers["Authorization"] == "Bearer from-env"  # type: ignore[reportPrivateUsage]
    finally:
        client.close()


def test_make_client_raises_auth_error_when_no_token(isolated_home: Path) -> None:
    with pytest.raises(AuthError) as info:
        make_client(_ctx())
    assert "Not logged in" in info.value.message
    assert info.value.exit_code == 3


def test_make_client_scopes_token_per_profile(isolated_home: Path) -> None:
    store_token("staging", "stg-token")

    # default profile has no token => raises
    with pytest.raises(AuthError):
        make_client(_ctx(profile="default"))

    # staging profile has one => works
    client = make_client(_ctx(profile="staging"))
    try:
        assert client._client.headers["Authorization"] == "Bearer stg-token"  # type: ignore[reportPrivateUsage]
    finally:
        client.close()
