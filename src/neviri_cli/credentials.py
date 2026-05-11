"""Token storage backends.

Two implementations behind a common ``TokenStore`` protocol:

- :class:`KeyringTokenStore` (default) — uses ``keyring``: macOS Keychain,
  Windows Credential Manager, Linux Secret Service.
- :class:`FileTokenStore` — fallback for headless CI where no keyring backend
  is available. Activated by ``NEVIRI_TOKEN_STORE=file``. Stores tokens at
  ``~/.neviri/credentials.json`` with 0600 perms.

Tokens are namespaced per *profile* (``default``, ``staging``, ``prod``).
The same machine can hold credentials for multiple profiles independently.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

import keyring
import keyring.errors

SERVICE_NAME = "neviri-cli"


@runtime_checkable
class TokenStore(Protocol):
    def get(self, profile: str) -> str | None: ...
    def set(self, profile: str, token: str) -> None: ...
    def delete(self, profile: str) -> None: ...


class KeyringTokenStore:
    """OS keychain-backed store."""

    def get(self, profile: str) -> str | None:
        try:
            return keyring.get_password(SERVICE_NAME, profile)
        except keyring.errors.KeyringError:
            return None

    def set(self, profile: str, token: str) -> None:
        keyring.set_password(SERVICE_NAME, profile, token)

    def delete(self, profile: str) -> None:
        try:
            keyring.delete_password(SERVICE_NAME, profile)
        except keyring.errors.PasswordDeleteError:
            pass
        except keyring.errors.KeyringError:
            pass


class FileTokenStore:
    """Plaintext-on-disk fallback for headless CI."""

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self._path = path
        else:
            env = os.environ.get("NEVIRI_CREDENTIALS")
            self._path = Path(env) if env else Path.home() / ".neviri" / "credentials.json"

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    def get(self, profile: str) -> str | None:
        return self._load().get(profile)

    def set(self, profile: str, token: str) -> None:
        data = self._load()
        data[profile] = token
        self._save(data)

    def delete(self, profile: str) -> None:
        data = self._load()
        data.pop(profile, None)
        self._save(data)


def get_token_store() -> TokenStore:
    """Return the active token store backend.

    File store kicks in when ``NEVIRI_TOKEN_STORE=file``; keyring otherwise.
    """
    backend = os.environ.get("NEVIRI_TOKEN_STORE", "").lower()
    if backend == "file":
        return FileTokenStore()
    return KeyringTokenStore()
