"""Tests for neviri_cli.credentials — token store backends + dispatch."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import keyring.errors
import pytest

from neviri_cli.credentials import (
    SERVICE_NAME,
    FileTokenStore,
    KeyringTokenStore,
    get_token_store,
)

# ---------- FileTokenStore ----------


def test_file_store_set_get_delete(tmp_path: Path) -> None:
    path = tmp_path / "creds.json"
    store = FileTokenStore(path=path)

    assert store.get("default") is None
    store.set("default", "tok-1")
    assert store.get("default") == "tok-1"
    store.delete("default")
    assert store.get("default") is None


def test_file_store_multiple_profiles(tmp_path: Path) -> None:
    path = tmp_path / "creds.json"
    store = FileTokenStore(path=path)
    store.set("default", "a")
    store.set("staging", "b")
    assert store.get("default") == "a"
    assert store.get("staging") == "b"


def test_file_store_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "creds.json"
    FileTokenStore(path=path).set("default", "abc")
    assert FileTokenStore(path=path).get("default") == "abc"


def test_file_store_safe_perms_on_posix(tmp_path: Path) -> None:
    path = tmp_path / "creds.json"
    store = FileTokenStore(path=path)
    store.set("default", "secret")
    if os.name != "nt":
        # 0o600 = rw for owner only
        assert path.stat().st_mode & 0o777 == 0o600


def test_file_store_handles_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "creds.json"
    path.write_text("{{{not json")
    store = FileTokenStore(path=path)
    assert store.get("default") is None


def test_file_store_delete_nonexistent_is_noop(tmp_path: Path) -> None:
    store = FileTokenStore(path=tmp_path / "creds.json")
    store.delete("default")  # should not raise
    assert store.get("default") is None


def test_file_store_uses_env_var_when_no_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "envcreds.json"
    monkeypatch.setenv("NEVIRI_CREDENTIALS", str(custom))
    store = FileTokenStore()
    store.set("default", "x")
    assert custom.exists()


# ---------- KeyringTokenStore ----------


def test_keyring_store_set_uses_keyring_module() -> None:
    with patch("neviri_cli.credentials.keyring.set_password") as set_pw:
        KeyringTokenStore().set("default", "tok")
    set_pw.assert_called_once_with(SERVICE_NAME, "default", "tok")


def test_keyring_store_get_returns_keyring_value() -> None:
    with patch("neviri_cli.credentials.keyring.get_password", return_value="tok") as get_pw:
        result = KeyringTokenStore().get("default")
    assert result == "tok"
    get_pw.assert_called_once_with(SERVICE_NAME, "default")


def test_keyring_store_get_returns_none_on_keyring_error() -> None:
    with patch(
        "neviri_cli.credentials.keyring.get_password",
        side_effect=keyring.errors.KeyringError(),
    ):
        assert KeyringTokenStore().get("default") is None


def test_keyring_store_delete_swallows_password_delete_error() -> None:
    with patch(
        "neviri_cli.credentials.keyring.delete_password",
        side_effect=keyring.errors.PasswordDeleteError(),
    ):
        KeyringTokenStore().delete("default")  # no exception


def test_keyring_store_delete_swallows_keyring_error() -> None:
    with patch(
        "neviri_cli.credentials.keyring.delete_password",
        side_effect=keyring.errors.KeyringError(),
    ):
        KeyringTokenStore().delete("default")


# ---------- Dispatch ----------


def test_get_token_store_default_is_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEVIRI_TOKEN_STORE", raising=False)
    assert isinstance(get_token_store(), KeyringTokenStore)


def test_get_token_store_file_when_env_says_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEVIRI_TOKEN_STORE", "file")
    assert isinstance(get_token_store(), FileTokenStore)


def test_get_token_store_env_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEVIRI_TOKEN_STORE", "FILE")
    assert isinstance(get_token_store(), FileTokenStore)


def test_get_token_store_unknown_value_falls_back_to_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEVIRI_TOKEN_STORE", "weird")
    assert isinstance(get_token_store(), KeyringTokenStore)
