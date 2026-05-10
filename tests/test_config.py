"""Tests for neviri_cli.config — TOML round-trip, defaults, env override."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from neviri_cli.config import (
    CLIConfig,
    ProfileConfig,
    get_config_path,
    get_profile,
    load_config,
    save_config,
)


def test_get_config_path_uses_env_when_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom.toml"
    monkeypatch.setenv("NEVIRI_CONFIG", str(custom))
    assert get_config_path() == custom


def test_get_config_path_default_under_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEVIRI_CONFIG", raising=False)
    assert get_config_path() == Path.home() / ".neviri" / "config.toml"


def test_load_returns_defaults_when_missing(isolated_home: Path) -> None:
    cfg = load_config()
    assert cfg.default_profile == "default"
    assert "default" in cfg.profiles
    assert cfg.profiles["default"].api_url.startswith("http")


def test_save_and_reload_round_trip(isolated_home: Path) -> None:
    cfg = CLIConfig(
        default_profile="staging",
        profiles={
            "default": ProfileConfig(),
            "staging": ProfileConfig(
                api_url="https://stagingapi.neviri.com",
                auth_url="https://stagingauth.neviri.com",
                email="alice@example.com",
                user_id=7,
                account_id=3,
                name="Alice",
            ),
        },
    )
    save_config(cfg)

    reloaded = load_config()
    assert reloaded.default_profile == "staging"
    assert reloaded.profiles["staging"].email == "alice@example.com"
    assert reloaded.profiles["staging"].user_id == 7
    assert reloaded.profiles["staging"].account_id == 3


def test_save_excludes_none_so_disk_stays_minimal(isolated_home: Path) -> None:
    cfg = CLIConfig()
    save_config(cfg)
    contents = get_config_path().read_text()
    assert "user_id" not in contents
    assert "email" not in contents
    assert "default_profile" in contents


def test_get_profile_returns_default_when_missing(isolated_home: Path) -> None:
    cfg = CLIConfig()
    p = get_profile(cfg, "nonexistent")
    assert isinstance(p, ProfileConfig)
    assert p.email is None


def test_get_profile_returns_existing(isolated_home: Path) -> None:
    cfg = CLIConfig(
        profiles={"prod": ProfileConfig(email="prod@x.com")},
    )
    p = get_profile(cfg, "prod")
    assert p.email == "prod@x.com"


def test_extra_keys_rejected_at_load_time(isolated_home: Path) -> None:
    # Hand-craft a TOML with an unknown profile field.
    get_config_path().write_text('[profiles.default]\nrogue_field = "x"\n', encoding="utf-8")
    with pytest.raises(ValidationError):  # pydantic ValidationError
        load_config()


def test_invalid_output_format_rejected(isolated_home: Path) -> None:
    get_config_path().write_text('[profiles.default]\noutput = "xml"\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config()
