"""Tests for the `neviri config` subcommand."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.config import get_profile, load_config


def test_config_set_and_get_round_trip(isolated_home: Path, runner: CliRunner) -> None:
    set_result = runner.invoke(app, ["config", "set", "api_url", "https://api.example.com"])
    assert set_result.exit_code == 0, set_result.stdout

    get_result = runner.invoke(app, ["config", "get", "api_url"])
    assert get_result.exit_code == 0
    assert get_result.stdout.strip() == "https://api.example.com"


def test_config_set_int_field_coerces(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["config", "set", "user_id", "42"])
    assert result.exit_code == 0

    cfg = load_config()
    assert get_profile(cfg, "default").user_id == 42


def test_config_set_int_field_rejects_non_integer(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["config", "set", "user_id", "not-a-number"])
    assert result.exit_code != 0


def test_config_set_unknown_key_rejected(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["config", "set", "rogue", "x"])
    assert result.exit_code == 2


def test_config_get_unknown_key_rejected(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["config", "get", "rogue"])
    assert result.exit_code == 2


def test_config_get_unset_field_prints_empty_line(isolated_home: Path, runner: CliRunner) -> None:
    # email is None on a fresh profile
    result = runner.invoke(app, ["config", "get", "email"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_config_list_shows_all_profiles(isolated_home: Path, runner: CliRunner) -> None:
    runner.invoke(app, ["--profile", "staging", "config", "set", "api_url", "https://staging.x"])
    runner.invoke(app, ["--profile", "prod", "config", "set", "api_url", "https://prod.x"])

    result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "[staging]" in result.stdout
    assert "[prod]" in result.stdout
    assert "https://staging.x" in result.stdout
    assert "https://prod.x" in result.stdout


def test_config_use_context_switches_default(isolated_home: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["config", "use-context", "staging"])
    assert result.exit_code == 0

    cfg = load_config()
    assert cfg.default_profile == "staging"
    assert "staging" in cfg.profiles


def test_use_context_then_default_profile_resolves_correctly(
    isolated_home: Path, runner: CliRunner
) -> None:
    runner.invoke(app, ["config", "use-context", "staging"])
    # Without --profile, the next command should pick up staging from config.
    result = runner.invoke(app, ["config", "set", "api_url", "https://staging-default.x"])
    assert result.exit_code == 0

    cfg = load_config()
    assert cfg.profiles["staging"].api_url == "https://staging-default.x"
    assert cfg.profiles["default"].api_url != "https://staging-default.x"


def test_explicit_profile_overrides_default(isolated_home: Path, runner: CliRunner) -> None:
    runner.invoke(app, ["config", "use-context", "staging"])
    result = runner.invoke(app, ["--profile", "prod", "config", "set", "api_url", "https://prod.x"])
    assert result.exit_code == 0

    cfg = load_config()
    assert cfg.profiles["prod"].api_url == "https://prod.x"
    assert cfg.profiles["staging"].api_url != "https://prod.x"
