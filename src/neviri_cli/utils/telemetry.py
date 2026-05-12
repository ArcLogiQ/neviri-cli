"""Opt-in telemetry.

**This is the single source of truth for what the CLI sends and when.** It
is intentionally short and easy to audit; ``docs/privacy.md`` mirrors what
this file actually does. If you change the payload, change the doc.

# Contract

The CLI sends ZERO telemetry by default. Even after a user opts in, the
payload contains only:

- ``command`` — the top-level subcommand name (e.g. ``vm``, ``db``); never
  arguments, flag values, IDs, or any user-supplied string
- ``cli_version`` — the value of ``neviri_cli.__version__``
- ``os`` — ``linux`` / ``darwin`` / ``windows``
- ``install_id`` — a random UUIDv4 generated locally at opt-in time; never
  tied to a user account, email, or token

That's it. No IPs, no hostnames, no timestamps beyond what the HTTP
endpoint already sees, no command arguments, no file paths.

# Always disabled when

Telemetry is **always** disabled (no prompt, no send) when any of these
hold:

- ``$NEVIRI_TELEMETRY=disable`` (or ``off``/``false``/``0``)
- ``$CI=true`` (and most CI-system equivalents)
- stdin or stderr is not a TTY (non-interactive, piped, or daemon
  contexts)

# Opt-in flow

On the first interactive (TTY) invocation, the CLI prompts:

    Help improve neviri? Send anonymous usage stats?  [y/N]

Default answer is **No**. The decision is persisted in
``~/.neviri/config.toml`` as ``telemetry = true|false``. The user can
flip it any time with ``neviri config set telemetry false``.

# Fire-and-forget

Telemetry is sent on a background daemon thread with a 2-second timeout.
Failures are swallowed silently — telemetry is NEVER allowed to crash or
slow down the CLI.
"""

from __future__ import annotations

import os
import platform
import sys
import threading
import uuid
from typing import Any

import httpx

from neviri_cli import __version__

DEFAULT_ENDPOINT = "https://telemetry.neviri.com/cli/v1/events"
ENV_DISABLE = "NEVIRI_TELEMETRY"
ENV_ENDPOINT = "NEVIRI_TELEMETRY_ENDPOINT"
ENV_CI = "CI"

# Commands that should not trigger the first-run prompt (don't interrupt
# discovery / setup flows).
_QUIET_COMMANDS = frozenset({"version", "completion", "config", "auth"})


def is_telemetry_disabled_by_env() -> bool:
    """Always-disable env signals take precedence over config."""
    disable_signal = os.environ.get(ENV_DISABLE, "").lower()
    if disable_signal in ("disable", "off", "false", "0", "no"):
        return True
    ci_signal = os.environ.get(ENV_CI, "").lower()
    if ci_signal in ("true", "1", "yes"):
        return True
    return False


def is_interactive_tty() -> bool:
    """True only if BOTH stdin and stderr are real terminals."""
    try:
        return sys.stdin.isatty() and sys.stderr.isatty()
    except (AttributeError, OSError):
        return False


def resolve_endpoint() -> str | None:
    """Return the endpoint URL, or None when sending is disabled.

    Set ``NEVIRI_TELEMETRY_ENDPOINT=""`` (empty) to opt out of sending
    even after config-level opt-in. Useful for offline/air-gapped users.
    """
    if ENV_ENDPOINT in os.environ:
        return os.environ[ENV_ENDPOINT] or None
    return DEFAULT_ENDPOINT


def make_payload(*, command: str, install_id: str) -> dict[str, Any]:
    """Build the exactly-allowed payload.

    Tested separately so contributors can see at a glance what we send.
    """
    return {
        "command": command,
        "cli_version": __version__,
        "os": platform.system().lower(),
        "install_id": install_id,
    }


def _post(endpoint: str, payload: dict[str, Any], *, timeout: float = 2.0) -> None:
    """Best-effort HTTP POST. Errors are swallowed by design.

    Runs on a background thread; raising here would propagate to the
    thread but never to the user's main flow.
    """
    # Broad except: telemetry MUST NOT crash the CLI under any circumstance.
    try:
        httpx.post(endpoint, json=payload, timeout=timeout)
    except Exception:  # nosec B110 - telemetry is best-effort by design
        pass


def send_async(endpoint: str, payload: dict[str, Any]) -> None:
    """Spawn a daemon thread that POSTs the payload and exits."""
    thread = threading.Thread(target=_post, args=(endpoint, payload), daemon=True)
    thread.start()


def prompt_user() -> bool:
    """Interactive Y/N prompt. Default = No. Only call when TTY-safe."""
    import typer

    typer.echo(
        "\nHelp improve neviri by sending anonymous usage stats? We collect: "
        "command name, version, OS, an anonymous install ID — and nothing else. "
        "See https://docs.neviri.com/cli/privacy for details.",
        err=True,
    )
    return typer.confirm("Send anonymous usage stats?", default=False, err=True)


def record_command(command: str | None) -> None:
    """Top-level entry point — call from the Typer root callback.

    Does nothing if telemetry is disabled. Otherwise:
    - On first run in a TTY (and not a quiet command), prompts and persists
      the decision.
    - If enabled, fires a daemon-thread POST and returns immediately.

    NEVER raises. NEVER blocks.
    """
    if not command or command == "(no command)":
        return
    if is_telemetry_disabled_by_env():
        return

    # Lazy imports to keep this module's startup cost minimal.
    from neviri_cli.config import load_config, save_config

    # Broad except: if the config is corrupt, the CLI's main flow will surface
    # a clearer error elsewhere. Telemetry just goes silent.
    try:
        cfg = load_config()
    except Exception:
        return

    if cfg.telemetry is None:
        # First run. Prompt only when interactive AND the user isn't in
        # the middle of a quiet discovery / setup command.
        if command in _QUIET_COMMANDS:
            return
        if not is_interactive_tty():
            return
        try:
            decision = prompt_user()
        except (EOFError, KeyboardInterrupt):
            return
        cfg.telemetry = decision
        if decision and not cfg.install_id:
            cfg.install_id = str(uuid.uuid4())
        # Broad except: if persistence fails we just skip this run.
        try:
            save_config(cfg)
        except Exception:
            return

    if not cfg.telemetry:
        return

    # Ensure install_id exists (config may have been hand-edited)
    if not cfg.install_id:
        cfg.install_id = str(uuid.uuid4())
        # Broad except: if persistence fails we just skip this run.
        try:
            save_config(cfg)
        except Exception:
            return

    endpoint = resolve_endpoint()
    if not endpoint:
        return

    payload = make_payload(command=command, install_id=cfg.install_id)
    send_async(endpoint, payload)


__all__ = [
    "DEFAULT_ENDPOINT",
    "ENV_CI",
    "ENV_DISABLE",
    "ENV_ENDPOINT",
    "is_interactive_tty",
    "is_telemetry_disabled_by_env",
    "make_payload",
    "prompt_user",
    "record_command",
    "resolve_endpoint",
    "send_async",
]
