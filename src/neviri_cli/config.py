"""TOML-backed CLI configuration.

Layout:

    [profiles.default]
    api_url   = "http://localhost:8000"
    auth_url  = "http://localhost:8081"
    output    = "table"
    user_id   = 7
    email     = "alice@example.com"
    account_id = 3
    name      = "Alice"

    default_profile = "default"

Tokens are NEVER written here; they live in the OS keyring (or the file fallback
store, behind ``NEVIRI_TOKEN_STORE=file``). See :mod:`neviri_cli.credentials`.

The path is resolved from ``$NEVIRI_CONFIG`` first, then ``~/.neviri/config.toml``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel, ConfigDict, Field

from neviri_cli.output import OutputFormat


class ProfileConfig(BaseModel):
    """Per-profile config. All fields optional with sensible defaults."""

    model_config = ConfigDict(extra="forbid")

    api_url: str = "http://localhost:8000"
    auth_url: str = "http://localhost:8081"
    output: OutputFormat = "table"

    # Identity cache populated at login time so `neviri auth whoami`
    # doesn't have to make a network call.
    user_id: int | None = None
    email: str | None = None
    account_id: int | None = None
    name: str | None = None


class CLIConfig(BaseModel):
    """Top-level CLI config."""

    model_config = ConfigDict(extra="forbid")

    default_profile: str = "default"
    profiles: dict[str, ProfileConfig] = Field(default_factory=lambda: {"default": ProfileConfig()})


def get_config_path() -> Path:
    env = os.environ.get("NEVIRI_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".neviri" / "config.toml"


def load_config() -> CLIConfig:
    """Read config from disk; return defaults if the file doesn't exist."""
    path = get_config_path()
    if not path.exists():
        return CLIConfig()
    with path.open("rb") as f:
        data: dict[str, Any] = tomllib.load(f)
    return CLIConfig.model_validate(data)


def save_config(cfg: CLIConfig) -> None:
    """Write config to disk, creating parent dirs with safe perms."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = cfg.model_dump(exclude_none=True)
    with path.open("wb") as f:
        tomli_w.dump(payload, f)
    # Best-effort: mark file user-only on POSIX. No-op on Windows.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get_profile(cfg: CLIConfig, name: str) -> ProfileConfig:
    """Return the profile by name, or a fresh ProfileConfig if not present."""
    return cfg.profiles.get(name) or ProfileConfig()
