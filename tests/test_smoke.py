"""Smoke tests for the Neviri CLI root app."""

from typer.testing import CliRunner

from neviri_cli import __version__
from neviri_cli.app import app


def test_version_flag(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_flag_short(runner: CliRunner) -> None:
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "neviri" in result.stdout.lower()


def test_version_constant_format() -> None:
    assert __version__
    assert isinstance(__version__, str)
