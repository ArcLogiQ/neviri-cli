"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect config + credentials to a temp dir so tests don't touch
    the real ~/.neviri.

    Sets ``NEVIRI_CONFIG`` and ``NEVIRI_CREDENTIALS`` to paths under
    ``tmp_path`` and forces the file-based token store so tests don't touch
    the real OS keyring.
    """
    cfg_path = tmp_path / "config.toml"
    creds_path = tmp_path / "credentials.json"
    monkeypatch.setenv("NEVIRI_CONFIG", str(cfg_path))
    monkeypatch.setenv("NEVIRI_CREDENTIALS", str(creds_path))
    monkeypatch.setenv("NEVIRI_TOKEN_STORE", "file")
    monkeypatch.delenv("NEVIRI_API_TOKEN", raising=False)
    # Always disable telemetry in tests so we never accidentally send
    # anything to the real endpoint and tests don't depend on TTY state.
    monkeypatch.setenv("NEVIRI_TELEMETRY", "disable")
    yield tmp_path
