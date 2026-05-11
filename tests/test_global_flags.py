"""Tests for the global --output / --no-color / --debug / --profile flags
wired on the Typer root callback.
"""

from __future__ import annotations

from pathlib import Path

import typer
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.context import CLIContext


def _attach_probe() -> list[CLIContext]:
    """Attach a probe subcommand that captures the context for assertions."""
    captured: list[CLIContext] = []

    @app.command("__probe__", hidden=True)
    def probe(ctx: typer.Context) -> None:
        assert isinstance(ctx.obj, CLIContext)
        captured.append(ctx.obj)

    return captured


def test_defaults(isolated_home: Path, runner: CliRunner) -> None:
    captured = _attach_probe()
    result = runner.invoke(app, ["__probe__"])
    assert result.exit_code == 0
    assert captured[-1].output == "table"
    assert captured[-1].no_color is False
    assert captured[-1].debug is False
    assert captured[-1].profile == "default"


def test_output_json(isolated_home: Path, runner: CliRunner) -> None:
    captured = _attach_probe()
    result = runner.invoke(app, ["--output", "json", "__probe__"])
    assert result.exit_code == 0
    assert captured[-1].output == "json"


def test_output_short_flag(isolated_home: Path, runner: CliRunner) -> None:
    captured = _attach_probe()
    result = runner.invoke(app, ["-o", "yaml", "__probe__"])
    assert result.exit_code == 0
    assert captured[-1].output == "yaml"


def test_no_color(isolated_home: Path, runner: CliRunner) -> None:
    captured = _attach_probe()
    result = runner.invoke(app, ["--no-color", "__probe__"])
    assert result.exit_code == 0
    assert captured[-1].no_color is True


def test_debug(isolated_home: Path, runner: CliRunner) -> None:
    captured = _attach_probe()
    result = runner.invoke(app, ["--debug", "__probe__"])
    assert result.exit_code == 0
    assert captured[-1].debug is True


def test_profile(isolated_home: Path, runner: CliRunner) -> None:
    captured = _attach_probe()
    result = runner.invoke(app, ["--profile", "staging", "__probe__"])
    assert result.exit_code == 0
    assert captured[-1].profile == "staging"


def test_profile_falls_back_to_config_default(isolated_home: Path, runner: CliRunner) -> None:
    # Set the config's default_profile and verify --profile-less invocations pick it up.
    runner.invoke(app, ["config", "use-context", "staging"])
    captured = _attach_probe()
    result = runner.invoke(app, ["__probe__"])
    assert result.exit_code == 0
    assert captured[-1].profile == "staging"


def test_invalid_output_format_rejected(isolated_home: Path, runner: CliRunner) -> None:
    _attach_probe()
    result = runner.invoke(app, ["--output", "xml", "__probe__"])
    assert result.exit_code != 0
