"""Tests for the `neviri version` command."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.utils.version_check import GITHUB_API_LATEST_RELEASE

# ---------- default (no flags) ----------


def test_version_command_prints_current(isolated_home: Path, runner: CliRunner) -> None:
    from neviri_cli import __version__

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_command_check_and_upgrade_are_mutually_exclusive(
    isolated_home: Path, runner: CliRunner
) -> None:
    result = runner.invoke(app, ["version", "--check", "--upgrade"])
    assert result.exit_code == 2
    assert "mutually exclusive" in result.stderr


# ---------- --check ----------


@respx.mock
def test_version_check_reports_up_to_date(isolated_home: Path, runner: CliRunner) -> None:
    from neviri_cli import __version__

    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200,
            json={"tag_name": f"v{__version__}", "html_url": "u", "assets": []},
        )
    )
    result = runner.invoke(app, ["version", "--check"])
    assert result.exit_code == 0
    assert "up to date" in result.stdout


@respx.mock
def test_version_check_reports_upgrade_available_pip(
    isolated_home: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """For pip-installed users, suggest `pip install --upgrade`."""
    monkeypatch.delattr("sys.frozen", raising=False)
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v99.0.0",
                "html_url": "https://github.com/x/y/releases/tag/v99.0.0",
                "assets": [],
            },
        )
    )
    result = runner.invoke(app, ["version", "--check"])
    assert result.exit_code == 0
    assert "newer version" in result.stdout
    assert "99.0.0" in result.stdout
    assert "pip install --upgrade" in result.stdout
    assert "neviri version --upgrade" not in result.stdout


@respx.mock
def test_version_check_reports_upgrade_available_binary(
    isolated_home: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """For binary-installed users, suggest `neviri version --upgrade`."""
    monkeypatch.setattr("sys.frozen", True, raising=False)
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200,
            json={"tag_name": "v99.0.0", "html_url": "url", "assets": []},
        )
    )
    result = runner.invoke(app, ["version", "--check"])
    assert result.exit_code == 0
    assert "neviri version --upgrade" in result.stdout


@respx.mock
def test_version_check_network_failure_returns_exit_4(
    isolated_home: Path, runner: CliRunner
) -> None:
    respx.get(GITHUB_API_LATEST_RELEASE).mock(side_effect=httpx.ConnectError("dns"))
    result = runner.invoke(app, ["version", "--check"])
    assert result.exit_code == 4


# ---------- --upgrade ----------


@respx.mock
def test_version_upgrade_when_not_binary_returns_exit_2(
    isolated_home: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200, json={"tag_name": "v99.0.0", "html_url": "u", "assets": []}
        )
    )
    result = runner.invoke(app, ["version", "--upgrade"])
    assert result.exit_code == 2
    assert "binary installs" in result.stderr


@respx.mock
def test_version_upgrade_when_already_latest(
    isolated_home: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    from neviri_cli import __version__

    monkeypatch.setattr("sys.frozen", True, raising=False)
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200, json={"tag_name": f"v{__version__}", "html_url": "u", "assets": []}
        )
    )
    result = runner.invoke(app, ["version", "--upgrade"])
    assert result.exit_code == 0
    assert "already the latest" in result.stdout


@respx.mock
@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX-only os.replace path")
def test_version_upgrade_happy_path_posix(
    isolated_home: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Full upgrade flow on a POSIX runner."""
    fake_binary = tmp_path / "neviri"
    fake_binary.write_bytes(b"old binary")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_binary))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    payload = b"new binary"
    respx.get(GITHUB_API_LATEST_RELEASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v99.0.0",
                "html_url": "u",
                "assets": [
                    {
                        "name": "neviri-linux-x86_64",
                        "browser_download_url": "https://x/neviri-linux-x86_64",
                    }
                ],
            },
        )
    )
    respx.get("https://x/neviri-linux-x86_64").mock(
        return_value=httpx.Response(200, content=payload)
    )

    result = runner.invoke(app, ["version", "--upgrade"])
    assert result.exit_code == 0, result.stdout
    assert fake_binary.read_bytes() == payload
    assert "Upgrading to 99.0.0" in result.stdout


# ---------- regression: existing --version flag still works ----------


def test_root_version_flag_unchanged(runner: CliRunner) -> None:
    """Adding `neviri version` subcommand mustn't break `neviri --version`."""
    from neviri_cli import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
