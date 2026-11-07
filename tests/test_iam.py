from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import get_active_token, store_token
from neviri_cli.client.factory import make_client
from neviri_cli.config import CLIConfig, ProfileConfig, load_config, save_config
from neviri_cli.context import CLIContext
from neviri_cli.exceptions import AuthError, ServerError, UserError
from neviri_cli.iam import (
    IAMCredentials,
    IAMKeyringStore,
    assume_role,
    exchange_access_key,
    iam_store,
    load_iam_credentials,
    login_console,
    logout_iam,
    resolve_iam_token,
    save_iam_credentials,
    validate_iam_origin,
)
from neviri_cli.utils.redact import redact

IAM = "https://iam.test"
API = "https://api.test"


@pytest.fixture(autouse=True)
def isolated_iam(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEVIRI_IAM_TOKEN_STORE", "file")
    monkeypatch.setenv("NEVIRI_IAM_CREDENTIALS", str(isolated_home / "iam-credentials.json"))
    for name in (
        "NEVIRI_IAM_SESSION_TOKEN",
        "NEVIRI_IAM_ACCESS_KEY_ID",
        "NEVIRI_IAM_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def profile(**values) -> ProfileConfig:
    return ProfileConfig(auth_mode="iam", iam_url=IAM, api_url=API, **values)


def summary(role=False):
    return {
        "kind": "user",
        "account_id": 123,
        "principal_type": "iam_role_session" if role else "iam_user",
        "principal_arn": f"nvr:iam::123:{'role/Read' if role else 'user/dev'}",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
    }


def stored(**values):
    return IAMCredentials(iam_origin=IAM, api_origin=API, **values)


def mock_exchange(mock, role=False):
    data = summary(role)
    token = "role-token" if role else "user-token"
    mock.post(IAM + ("/v1/sts/assume-role" if role else "/v1/sts/token")).respond(
        200, json={"access_token": token, "expires_at": data["expires_at"]}
    )
    mock.get(IAM + "/v1/session").mock(return_value=httpx.Response(200, json=data))


def test_legacy_profile_defaults_and_stores_remain_independent(monkeypatch):
    assert ProfileConfig().auth_mode == "legacy"
    store_token("default", "legacy-credential")
    save_iam_credentials("default", stored(access_token="iam-credential"))
    assert get_active_token("default") == "legacy-credential"
    assert load_iam_credentials("default").access_token == "iam-credential"
    monkeypatch.setenv("NEVIRI_API_TOKEN", "legacy-env")
    with pytest.raises(AuthError):
        resolve_iam_token("missing", profile())
    assert get_active_token("default") == "legacy-env"


@respx.mock
def test_key_exchange_binds_session_and_refreshes_expired_token():
    mock_exchange(respx)
    save_iam_credentials(
        "iam",
        stored(
            access_key_id="NVIAEXAMPLE",
            secret_access_key="key-secret",
            access_token="expired",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        ),
    )
    assert resolve_iam_token("iam", profile()) == "user-token"
    assert respx.calls[0].request.url.path == "/v1/sts/token"
    assert b"key-secret" in respx.calls[0].request.content
    respx.reset()
    # Fresh cached token makes no IAM network call.
    assert resolve_iam_token("iam", profile()) == "user-token"
    assert len(respx.calls) == 0


@respx.mock
def test_iam_environment_key_pair_is_not_persisted(monkeypatch):
    monkeypatch.setenv("NEVIRI_IAM_ACCESS_KEY_ID", "NVIAEXAMPLE")
    monkeypatch.setenv("NEVIRI_IAM_SECRET_ACCESS_KEY", "env-secret")
    mock_exchange(respx)
    assert resolve_iam_token("iam", profile()) == "user-token"
    assert iam_store().get("iam") is None


@respx.mock
def test_explicit_iam_token_override_is_introspected_and_isolated(monkeypatch):
    monkeypatch.setenv("NEVIRI_IAM_SESSION_TOKEN", "explicit-session")
    monkeypatch.setenv("NEVIRI_API_TOKEN", "legacy-env")
    respx.get(IAM + "/v1/session").respond(200, json=summary())
    assert resolve_iam_token("iam", profile()) == "explicit-session"
    assert respx.calls[0].request.headers["authorization"] == "Bearer explicit-session"
    assert iam_store().get("iam") is None


@respx.mock
def test_partial_iam_env_pair_fails_without_legacy_fallback(monkeypatch):
    monkeypatch.setenv("NEVIRI_IAM_ACCESS_KEY_ID", "NVIAEXAMPLE")
    monkeypatch.setenv("NEVIRI_API_TOKEN", "legacy-env")
    with pytest.raises(AuthError):
        resolve_iam_token("iam", profile())
    assert not respx.calls


@respx.mock
def test_endpoint_change_never_sends_stored_secret_to_new_issuer():
    save_iam_credentials("iam", stored(access_key_id="NVIAEXAMPLE", secret_access_key="secret"))
    changed = profile().model_copy(update={"iam_url": "https://other.test"})
    with pytest.raises(AuthError):
        resolve_iam_token("iam", changed)
    assert not respx.calls


@respx.mock
def test_assume_role_applies_narrowing_policy_and_tracks_role_binding():
    source = stored(
        access_token="user-token",
        principal_type="iam_user",
        access_key_id="NVIAEXAMPLE",
        secret_access_key="secret",
    )
    document = {
        "Version": "2026-11-06",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "app-catalog:release-status",
                "Resource": "nvr:catalog:region-1:123:release_id/1",
            }
        ],
    }
    chosen = profile(
        iam_role_arn="nvr:iam::123:role/Read",
        iam_session_policy=document,
        iam_external_id="external",
    )
    mock_exchange(respx, role=True)
    issued = assume_role(chosen, source)
    assert issued.principal_type == "iam_role_session"
    assert issued.role_fingerprint
    assert b"app-catalog:release-status" in respx.calls[0].request.content
    assert b"external" in respx.calls[0].request.content
    assert issued.secret_access_key == "secret"


@respx.mock
def test_role_chaining_and_mismatched_role_are_rejected():
    chosen = profile(iam_role_arn="nvr:iam::123:role/Read")
    with pytest.raises(AuthError):
        assume_role(chosen, stored(access_token="role-token", principal_type="iam_role_session"))
    mock_exchange(respx, role=False)
    respx.post(IAM + "/v1/sts/assume-role").respond(
        200, json={"access_token": "unexpected", "expires_at": summary()["expires_at"]}
    )
    with pytest.raises(ServerError):
        assume_role(chosen, stored(access_token="user-token", principal_type="iam_user"))


@respx.mock
def test_console_login_account_binding_and_password_mfa_debug_redaction(capsys):
    data = summary()
    respx.post(IAM + "/v1/console/login").respond(
        200, json={"access_token": "temporary-token", "expires_at": data["expires_at"]}
    )
    respx.get(IAM + "/v1/session").respond(200, json=data)
    credentials = login_console(profile(), 123, "dev", "sensitive-password", "123456", debug=True)
    assert credentials.account_id == 123 and credentials.access_key_id is None
    output = capsys.readouterr().err
    assert (
        "sensitive-password" not in output
        and "123456" not in output
        and "temporary-token" not in output
    )
    with pytest.raises(ServerError):
        login_console(profile(), 124, "dev", "password")


@respx.mock
def test_logout_revokes_only_iam_and_clears_during_outage():
    store_token("iam", "legacy-token")
    save_iam_credentials("iam", stored(access_token="user-token"))
    respx.delete(IAM + "/v1/session").mock(side_effect=httpx.ConnectError("offline"))
    assert not logout_iam("iam", profile())
    assert iam_store().get("iam") is None
    assert get_active_token("iam") == "legacy-token"


@respx.mock
def test_iam_factory_uses_short_token_not_legacy_override(monkeypatch):
    save_config(CLIConfig(profiles={"iam": profile()}))
    save_iam_credentials(
        "iam",
        stored(access_token="user-token", expires_at=datetime.now(UTC) + timedelta(minutes=15)),
    )
    monkeypatch.setenv("NEVIRI_API_TOKEN", "legacy-env")
    context = SimpleNamespace(obj=CLIContext(profile="iam"))
    with make_client(context) as client:
        assert client._client.headers["authorization"] == "Bearer user-token"
    assert not respx.calls


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.test",
        "https://user:secret@iam.test",
        "https://iam.test/path",
        "https://iam.test?secret=x",
        "not-a-url",
    ],
)
def test_untrusted_or_insecure_iam_origins_are_rejected(url):
    with pytest.raises(UserError):
        validate_iam_origin(url)


def test_iam_profile_configure_never_moves_legacy_credentials(runner: CliRunner):
    store_token("default", "legacy-credential")
    result = runner.invoke(
        app, ["--profile", "default", "iam", "configure", "--iam-url", IAM, "--api-url", API]
    )
    assert result.exit_code == 0, result.output
    assert load_config().profiles["default"].auth_mode == "iam"
    assert get_active_token("default") == "legacy-credential"
    assert iam_store().get("default") is None


@respx.mock
def test_iam_login_stdin_and_catalog_command(runner: CliRunner):
    save_config(CLIConfig(profiles={"default": profile()}))
    mock_exchange(respx)
    result = runner.invoke(
        app,
        ["iam", "login", "--access-key-id", "NVIAEXAMPLE", "--secret-stdin"],
        input="secret-from-stdin\n",
    )
    assert result.exit_code == 0, result.output
    assert "secret-from-stdin" not in result.output
    status_route = respx.get(API + "/api/v1/catalog/releases/1/status").respond(
        200, json={"status": "running", "url": "https://app.test", "error": None}
    )
    output = runner.invoke(app, ["--output", "json", "catalog", "release-status", "1"])
    assert output.exit_code == 0, output.output
    assert "running" in output.output
    assert status_route.calls[0].request.headers["authorization"] == "Bearer user-token"


def test_iam_debug_fields_include_validation_echoes():
    data = redact(
        {
            "secret_access_key": "secret",
            "mfa_code": "123456",
            "secret": "seed",
            "provisioning_uri": "uri",
            "detail": [{"input": "echo-secret"}],
            "access_key_id": "NVIAID",
        }
    )
    assert data["secret_access_key"] == "***" and data["mfa_code"] == "***"
    assert data["detail"][0]["input"] == "***"
    assert data["access_key_id"] == "NVIAID"


def test_keyring_namespace_is_separate_and_errors_fail_closed(monkeypatch):
    import keyring

    calls = []
    monkeypatch.setattr(keyring, "set_password", lambda *args: calls.append(args))
    monkeypatch.setattr(keyring, "get_password", lambda *args: "iam-json")
    monkeypatch.setattr(keyring, "delete_password", lambda *args: calls.append(args))
    store = IAMKeyringStore()
    store.set("default", "iam-json")
    assert store.get("default") == "iam-json"
    store.delete("default")
    assert all(call[0] == "neviri-cli-iam" for call in calls)

    def unavailable(*args):
        raise keyring.errors.KeyringError("unavailable")

    monkeypatch.setattr(keyring, "get_password", unavailable)
    monkeypatch.setattr(keyring, "set_password", unavailable)
    monkeypatch.setattr(keyring, "delete_password", unavailable)
    with pytest.raises(AuthError):
        store.get("default")
    with pytest.raises(AuthError):
        store.set("default", "secret")
    with pytest.raises(AuthError):
        store.delete("default")


@respx.mock
def test_iam_whoami_and_logout_commands_keep_legacy_store(runner):
    save_config(CLIConfig(profiles={"default": profile()}))
    save_iam_credentials(
        "default",
        stored(access_token="user-token", expires_at=datetime.now(UTC) + timedelta(minutes=15)),
    )
    store_token("default", "legacy-stays")
    respx.get(IAM + "/v1/session").respond(200, json=summary())
    respx.delete(IAM + "/v1/session").respond(204)
    who = runner.invoke(app, ["--output", "json", "iam", "whoami"])
    assert who.exit_code == 0, who.output
    assert "nvr:iam::123:user/dev" in who.output and "user-token" not in who.output
    out = runner.invoke(app, ["iam", "logout"])
    assert out.exit_code == 0, out.output
    assert iam_store().get("default") is None
    assert get_active_token("default") == "legacy-stays"


@respx.mock
def test_iam_console_login_command_uses_hidden_password_and_mfa_prompts(runner, monkeypatch):
    from neviri_cli.commands import iam as commands

    save_config(CLIConfig(profiles={"default": profile()}))
    answers = iter(["StrongSecret123", "123456"])
    monkeypatch.setattr(commands.getpass, "getpass", lambda _: next(answers))
    respx.post(IAM + "/v1/console/login").respond(
        200, json={"access_token": "user-token", "expires_at": summary()["expires_at"]}
    )
    respx.get(IAM + "/v1/session").respond(200, json=summary())
    result = runner.invoke(
        app, ["iam", "login", "--username", "dev", "--account-id", "123", "--mfa"]
    )
    assert result.exit_code == 0, result.output
    assert "StrongSecret123" not in result.output and "123456" not in result.output
    assert load_iam_credentials("default").secret_access_key is None


@respx.mock
def test_assume_role_command_persists_only_nonsecret_profile_options(runner, tmp_path):
    import json

    save_config(CLIConfig(profiles={"default": profile()}))
    save_iam_credentials(
        "default", stored(access_key_id="NVIAEXAMPLE", secret_access_key="source-secret")
    )
    respx.post(IAM + "/v1/sts/token").respond(
        200, json={"access_token": "user-token", "expires_at": summary()["expires_at"]}
    )
    respx.post(IAM + "/v1/sts/assume-role").respond(
        200, json={"access_token": "role-token", "expires_at": summary(True)["expires_at"]}
    )
    respx.get(IAM + "/v1/session").mock(
        side_effect=lambda request: httpx.Response(
            200, json=summary(request.headers["authorization"] == "Bearer role-token")
        )
    )
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({"Version": "2026-11-06", "Statement": []}))
    result = runner.invoke(
        app, ["iam", "assume-role", "nvr:iam::123:role/Read", "--session-policy", str(policy_file)]
    )
    assert result.exit_code == 0, result.output
    assert load_config().profiles["default"].iam_role_arn == "nvr:iam::123:role/Read"
    assert load_iam_credentials("default").principal_type == "iam_role_session"
    assert "source-secret" not in (tmp_path / "config.toml").read_text()
    assert "role-token" not in result.output


@pytest.mark.parametrize("args", [["iam", "whoami"], ["iam", "logout"], ["iam", "login"]])
def test_iam_commands_require_explicit_profile_opt_in(runner, args):
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "explicit IAM profile" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["--username", "dev"],
        ["--account-id", "123"],
        ["--mfa"],
        ["--access-key-id", "NVIAEXAMPLE", "--secret-stdin"],
    ],
)
def test_invalid_iam_login_options_or_empty_secret_fail_without_requests(runner, args):
    save_config(CLIConfig(profiles={"default": profile()}))
    result = runner.invoke(app, ["iam", "login", *args], input="\n")
    assert result.exit_code == 2


@respx.mock
def test_invalid_key_and_missing_server_expiry_are_not_stored():
    with pytest.raises(UserError):
        exchange_access_key(
            profile(), IAMCredentials(access_key_id="nvr_legacy", secret_access_key="secret")
        )
    with pytest.raises(AuthError):
        exchange_access_key(profile(), IAMCredentials())
    respx.post(IAM + "/v1/sts/token").respond(
        200, json={"access_token": "user-token", "expires_at": "invalid"}
    )
    respx.get(IAM + "/v1/session").respond(200, json=summary())
    with pytest.raises(ServerError):
        exchange_access_key(
            profile(), IAMCredentials(access_key_id="NVIAEXAMPLE", secret_access_key="secret")
        )


def test_invalid_stored_iam_record_is_not_silently_treated_as_legacy():
    iam_store().set("default", "not-json")
    with pytest.raises(AuthError):
        load_iam_credentials("default")


@pytest.mark.parametrize("target", ["credentials.json", "config.toml"])
def test_iam_store_never_overwrites_legacy_credentials_or_config(
    isolated_home, monkeypatch, target
):
    protected = isolated_home / target
    protected.write_text("existing protected data")
    monkeypatch.setenv("NEVIRI_IAM_CREDENTIALS", str(protected))
    with pytest.raises(UserError):
        save_iam_credentials("default", stored(access_token="new-iam-secret"))
    assert protected.read_text() == "existing protected data"


def test_iam_store_rejects_hardlink_alias_of_legacy_file(isolated_home, monkeypatch):
    import os

    protected = isolated_home / "credentials.json"
    protected.write_text("existing protected data")
    alias = isolated_home / "alias.json"
    os.link(protected, alias)
    monkeypatch.setenv("NEVIRI_IAM_CREDENTIALS", str(alias))
    with pytest.raises(UserError):
        iam_store().delete("default")
    assert protected.read_text() == "existing protected data"


@respx.mock
def test_env_user_override_assumes_configured_role_with_narrowing_policy(monkeypatch):
    monkeypatch.setenv("NEVIRI_IAM_SESSION_TOKEN", "env-user")
    chosen = profile(
        iam_role_arn="nvr:iam::123:role/Read",
        iam_session_policy={"Version": "2026-11-06", "Statement": []},
    )
    respx.post(IAM + "/v1/sts/assume-role").respond(
        200, json={"access_token": "role-token", "expires_at": summary(True)["expires_at"]}
    )
    respx.get(IAM + "/v1/session").mock(
        side_effect=lambda request: httpx.Response(
            200, json=summary(request.headers["authorization"] == "Bearer role-token")
        )
    )
    assert resolve_iam_token("iam", chosen) == "role-token"
    assert iam_store().get("iam") is None


@respx.mock
@pytest.mark.parametrize("policy", [None, {"Statement": []}])
def test_env_role_override_must_prove_configured_role_and_policy(monkeypatch, policy):
    monkeypatch.setenv("NEVIRI_IAM_SESSION_TOKEN", "env-role")
    chosen = profile(
        iam_role_arn="nvr:iam::123:role/Other" if policy is None else "nvr:iam::123:role/Read",
        iam_session_policy=policy,
    )
    respx.get(IAM + "/v1/session").respond(200, json=summary(True))
    with pytest.raises(AuthError):
        resolve_iam_token("iam", chosen)


def test_missing_keyring_credential_delete_is_idempotent(monkeypatch):
    import keyring

    def missing(*args):
        raise keyring.errors.PasswordDeleteError("missing")

    monkeypatch.setattr(keyring, "delete_password", missing)
    monkeypatch.setattr(keyring, "get_password", lambda *args: None)
    IAMKeyringStore().delete("absent")


def test_failed_existing_keyring_delete_never_reports_local_cleanup(monkeypatch):
    import keyring

    def failed(*args):
        raise keyring.errors.PasswordDeleteError("failed")

    monkeypatch.setattr(keyring, "delete_password", failed)
    monkeypatch.setattr(keyring, "get_password", lambda *args: "retained-credential")
    with pytest.raises(AuthError):
        IAMKeyringStore().delete("existing")


def test_legacy_config_save_and_list_do_not_acquire_iam_fields(isolated_home, runner):
    save_config(CLIConfig())
    contents = (isolated_home / "config.toml").read_text()
    assert "auth_mode" not in contents and "iam_url" not in contents
    result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "auth_mode" not in result.output and "iam_url" not in result.output


@respx.mock
def test_identity_output_allowlists_metadata_even_if_upstream_adds_secrets(runner):
    save_config(CLIConfig(profiles={"default": profile()}))
    save_iam_credentials(
        "default",
        stored(access_token="user-token", expires_at=datetime.now(UTC) + timedelta(minutes=15)),
    )
    respx.get(IAM + "/v1/session").respond(
        200,
        json={
            **summary(),
            "access_token": "NEVER_DISPLAY_TOKEN",
            "secret_access_key": "NEVER_DISPLAY_KEY",
            "secret": "NEVER_DISPLAY_SEED",
        },
    )
    result = runner.invoke(app, ["--output", "json", "iam", "whoami"])
    assert result.exit_code == 0, result.output
    assert "NEVER_DISPLAY" not in result.output


SERVER_UUID = "00000000-0000-4000-8000-000000000123"
OPERATION_UUID = "00000000-0000-4000-8000-000000000456"


def operation(status="accepted", **changes):
    return {
        "message": "Server operation",
        "operation_id": OPERATION_UUID,
        "revision": 1,
        "server_id": SERVER_UUID,
        "operation_status": status,
        "action": "stop",
        "observed_status": "ACTIVE",
        "failure_code": None,
        "created_at": datetime.now(UTC).isoformat(),
        "confirmed_at": None,
        **changes,
    }


def cache_iam_profile():
    save_config(CLIConfig(profiles={"default": profile()}))
    save_iam_credentials(
        "default",
        stored(
            access_token="user-token",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        ),
    )


@respx.mock
def test_iam_vm_stop_has_fixed_body_explicit_key_and_safe_output(runner):
    cache_iam_profile()
    route = respx.post(API + f"/api/v1/compute/servers/{SERVER_UUID}/action").respond(
        200,
        json=operation(access_token="NEVER_TOKEN", message="NEVER_DETAIL"),
    )
    result = runner.invoke(
        app,
        ["--output", "json", "vm", "stop", SERVER_UUID, "--idempotency-key", "stop-request-001"],
    )
    assert result.exit_code == 0, result.output
    request = route.calls[0].request
    assert request.headers["Idempotency-Key"] == "stop-request-001"
    assert request.headers["Authorization"] == "Bearer user-token"
    assert request.content == b'{"action":"stop"}'
    assert not any(
        name in request.headers for name in ("X-Account-ID", "X-User-ID", "X-OpenStack-Region")
    )
    assert "NEVER" not in result.output and OPERATION_UUID in result.output
    assert route.call_count == 1


@respx.mock
def test_legacy_vm_stop_keeps_original_nonuuid_path_and_no_new_header(runner):
    save_config(CLIConfig(profiles={"default": ProfileConfig(api_url=API)}))
    store_token("default", "legacy-token")
    route = respx.post(API + "/api/v1/compute/servers/legacy-id/action").respond(
        200, json={"message": "Stopped"}
    )
    result = runner.invoke(app, ["vm", "stop", "legacy-id"])
    assert result.exit_code == 0, result.output
    assert "Idempotency-Key" not in route.calls[0].request.headers
    assert route.calls[0].request.headers["Authorization"] == "Bearer legacy-token"
    rejected = runner.invoke(app, ["vm", "stop", "legacy-id", "--idempotency-key", "explicit-key"])
    assert rejected.exit_code == 2 and route.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    "server,key",
    [
        (SERVER_UUID, None),
        (SERVER_UUID, "short"),
        (SERVER_UUID, "non-ascii-é"),
        (SERVER_UUID, "contains space"),
        ("path/credentials", "valid-key"),
        ("AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", "valid-key"),
    ],
)
def test_iam_stop_validates_selectors_before_any_auth_or_business_request(runner, server, key):
    save_config(CLIConfig(profiles={"default": profile()}))
    args = ["vm", "stop", server] + (["--idempotency-key", key] if key else [])
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert len(respx.calls) == 0


@respx.mock
@pytest.mark.parametrize("status", [409, 503])
def test_iam_stop_error_recovery_is_allowlisted_and_never_retried(runner, status):
    cache_iam_profile()
    route = respx.post(API + f"/api/v1/compute/servers/{SERVER_UUID}/action").respond(
        status,
        json=operation(
            "unknown",
            message="NEVER_DETAIL",
            detail={"input": {"password": "NEVER_PASSWORD"}},
            secret="NEVER_SECRET",
        ),
        headers={"X-Request-ID": "NEVER_HEADER"},
    )
    result = runner.invoke(
        app, ["--debug", "vm", "stop", SERVER_UUID, "--idempotency-key", "NEVER_IDEMPOTENCY_KEY"]
    )
    assert result.exit_code == (5 if status == 503 else 2)
    assert OPERATION_UUID in result.output and "unknown" in result.output
    assert "operation-status" in result.output and "NEVER" not in result.output
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    "metadata",
    [
        {"operation_id": OPERATION_UUID},
        {"operation_id": OPERATION_UUID, "operation_status": "NEVER_STATE"},
        {"operation_id": "NEVER_ID", "operation_status": "unknown"},
        ["NEVER_DETAIL"],
    ],
)
def test_iam_stop_error_metadata_requires_canonical_id_and_known_optional_state(runner, metadata):
    cache_iam_profile()
    respx.post(API + f"/api/v1/compute/servers/{SERVER_UUID}/action").respond(503, json=metadata)
    result = runner.invoke(app, ["vm", "stop", SERVER_UUID, "--idempotency-key", "request-key"])
    assert result.exit_code == 5 and "NEVER" not in result.output
    assert (OPERATION_UUID in result.output) == (
        isinstance(metadata, dict) and metadata.get("operation_id") == OPERATION_UUID
    )


@respx.mock
def test_iam_stop_network_failure_is_sanitized_and_not_retried(runner):
    cache_iam_profile()
    route = respx.post(API + f"/api/v1/compute/servers/{SERVER_UUID}/action").mock(
        side_effect=httpx.ConnectError("NEVER_NETWORK_SECRET")
    )
    result = runner.invoke(app, ["vm", "stop", SERVER_UUID, "--idempotency-key", "request-key"])
    assert result.exit_code == 4 and "NEVER" not in result.output
    assert "same idempotency key" in result.output and route.call_count == 1


@respx.mock
def test_iam_operation_status_fixed_path_and_separate_policy_denial(runner):
    cache_iam_profile()
    route = respx.get(API + f"/api/v1/compute/iam/operations/{OPERATION_UUID}").respond(
        200, json=operation()
    )
    result = runner.invoke(app, ["--output", "json", "iam", "operation-status", OPERATION_UUID])
    assert result.exit_code == 0 and OPERATION_UUID in result.output
    assert "Idempotency-Key" not in route.calls[0].request.headers
    route.respond(403, json={"detail": "NEVER_POLICY_DETAIL"})
    denied = runner.invoke(app, ["iam", "operation-status", OPERATION_UUID])
    assert denied.exit_code == 3 and "NEVER" not in denied.output


@respx.mock
@pytest.mark.parametrize(
    "change",
    [
        {"server_id": "invalid"},
        {"revision": True},
        {"created_at": "invalid"},
        {"confirmed_at": "invalid"},
        {"failure_code": "NEVER secret"},
        {"observed_status": {"password": "NEVER"}},
        {"action": "start"},
        {"server_id": "00000000-0000-4000-8000-000000000999"},
    ],
)
def test_invalid_stop_success_metadata_is_rejected_without_echoing_it(runner, change):
    cache_iam_profile()
    respx.post(API + f"/api/v1/compute/servers/{SERVER_UUID}/action").respond(
        200, json=operation(**change)
    )
    result = runner.invoke(app, ["vm", "stop", SERVER_UUID, "--idempotency-key", "request-key"])
    assert result.exit_code == 5 and "NEVER" not in result.output


@respx.mock
def test_invalid_operation_json_and_mismatched_lookup_id_are_safe(runner):
    cache_iam_profile()
    stop = respx.post(API + f"/api/v1/compute/servers/{SERVER_UUID}/action").respond(
        200, text="NEVER_RAW"
    )
    args = ["--debug", "vm", "stop", SERVER_UUID, "--idempotency-key", "request-key"]
    invalid = runner.invoke(app, args)
    assert invalid.exit_code == 5 and "NEVER" not in invalid.output
    stop.respond(503, text="NEVER_ERROR")
    invalid = runner.invoke(app, args)
    assert invalid.exit_code == 5 and "NEVER" not in invalid.output
    respx.get(API + f"/api/v1/compute/iam/operations/{OPERATION_UUID}").respond(
        200, json=operation(operation_id=SERVER_UUID)
    )
    mismatch = runner.invoke(app, ["iam", "operation-status", OPERATION_UUID])
    assert mismatch.exit_code == 5
