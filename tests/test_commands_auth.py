"""End-to-end tests for the `neviri auth` subcommand."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import ENV_TOKEN, get_active_token, store_token
from neviri_cli.config import get_profile, load_config


def _jwt(claims: dict[str, object]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"hdr.{body}.sig"


# ---------- login: api token ----------


def test_login_with_api_token_stores_it(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "login", "--api-token", "nvr_abc123"])
    assert result.exit_code == 0, result.stdout
    assert get_active_token("default") == "nvr_abc123"


def test_login_with_api_token_rejects_bad_prefix(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "login", "--api-token", "not-an-nvr-token"])
    assert result.exit_code == 2
    assert get_active_token("default") is None


def test_login_with_api_token_from_stdin(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        ["auth", "login", "--api-token", "-"],
        input="nvr_from_stdin\n",
    )
    assert result.exit_code == 0
    assert get_active_token("default") == "nvr_from_stdin"


def test_login_with_empty_stdin_token_rejected(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "login", "--api-token", "-"], input="\n")
    assert result.exit_code == 2


# ---------- login: password ----------


@respx.mock
def test_login_with_password_stores_token_and_caches_identity(
    isolated_home: Path, runner: CliRunner
) -> None:
    jwt = _jwt({"id": 7, "email": "alice@x.com", "accountId": 3})
    respx.post("http://localhost:8081/api/v1/user/login").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "token": jwt,
                "user": {"id": 7, "email": "alice@x.com", "name": "Alice"},
            },
        )
    )
    result = runner.invoke(
        app,
        ["auth", "login", "--email", "alice@x.com"],
        input="hunter2\n",
    )
    assert result.exit_code == 0, result.stdout

    assert get_active_token("default") == jwt
    cfg = load_config()
    profile = get_profile(cfg, "default")
    assert profile.email == "alice@x.com"
    assert profile.user_id == 7
    assert profile.account_id == 3
    assert profile.name == "Alice"


@respx.mock
def test_login_with_password_handles_failure(isolated_home: Path, runner: CliRunner) -> None:
    respx.post("http://localhost:8081/api/v1/user/login").mock(
        return_value=httpx.Response(401, json={"message": "Incorrect password!"})
    )
    result = runner.invoke(
        app,
        ["auth", "login", "--email", "alice@x.com"],
        input="wrong\n",
    )
    assert result.exit_code == 3  # AuthError


# ---------- logout ----------


def test_logout_clears_token(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "something")
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0
    assert get_active_token("default") is None


def test_logout_when_not_logged_in_is_idempotent(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0


# ---------- whoami ----------


def test_whoami_when_not_logged_in_returns_3(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "whoami"])
    assert result.exit_code == 3
    assert "Not logged in" in result.stderr


def test_whoami_with_env_token_says_so(
    isolated_home: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_TOKEN, "nvr_env")
    result = runner.invoke(app, ["auth", "whoami"])
    assert result.exit_code == 0
    assert "env var" in result.stdout
    assert "default" in result.stdout


def test_whoami_with_api_token_in_store(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "nvr_xyz")
    result = runner.invoke(app, ["auth", "whoami"])
    assert result.exit_code == 0
    assert "API token" in result.stdout


def test_whoami_with_jwt_uses_cached_identity(isolated_home: Path, runner: CliRunner) -> None:
    # Simulate prior login by writing identity to config + token to store.
    store_token("default", _jwt({"id": 7, "email": "x@y.com"}))
    cfg = load_config()
    cfg.profiles["default"].email = "x@y.com"
    cfg.profiles["default"].account_id = 3
    from neviri_cli.config import save_config

    save_config(cfg)

    result = runner.invoke(app, ["auth", "whoami"])
    assert result.exit_code == 0
    assert "x@y.com" in result.stdout
    assert "account: 3" in result.stdout


def test_whoami_with_jwt_no_cache_decodes_payload(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", _jwt({"email": "from-jwt@x.com"}))
    result = runner.invoke(app, ["auth", "whoami"])
    assert result.exit_code == 0
    assert "from-jwt@x.com" in result.stdout


# ---------- token ----------


def test_token_prints_active_token(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "nvr_print_me")
    result = runner.invoke(app, ["auth", "token"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "nvr_print_me"


def test_token_returns_3_when_not_logged_in(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "token"])
    assert result.exit_code == 3


# ---------- --profile flag scopes everything ----------


def test_profile_flag_scopes_token_storage(isolated_home: Path, runner: CliRunner) -> None:
    runner.invoke(app, ["--profile", "staging", "auth", "login", "--api-token", "nvr_staging"])
    runner.invoke(app, ["--profile", "prod", "auth", "login", "--api-token", "nvr_prod"])

    assert get_active_token("staging") == "nvr_staging"
    assert get_active_token("prod") == "nvr_prod"
    assert get_active_token("default") is None
