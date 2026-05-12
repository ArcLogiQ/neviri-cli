"""Tests for the opt-in telemetry layer.

Pin the contract that ``docs/privacy.md`` promises:
- Default is OFF
- Payload contains only ``command``, ``cli_version``, ``os``, ``install_id``
- CI / non-TTY / env-disabled environments never prompt and never send
- ``neviri config set telemetry false`` instantly disables
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from neviri_cli import __version__
from neviri_cli.config import load_config, save_config
from neviri_cli.utils.telemetry import (
    DEFAULT_ENDPOINT,
    ENV_CI,
    ENV_DISABLE,
    ENV_ENDPOINT,
    is_interactive_tty,
    is_telemetry_disabled_by_env,
    make_payload,
    record_command,
    resolve_endpoint,
    send_async,
)

# ---------- env-disable signals ----------


@pytest.mark.parametrize("value", ["disable", "off", "false", "0", "no", "DISABLE", "Off"])
def test_disabled_by_env_neviri_telemetry(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DISABLE, value)
    monkeypatch.delenv(ENV_CI, raising=False)
    assert is_telemetry_disabled_by_env()


@pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE"])
def test_disabled_by_env_ci(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.setenv(ENV_CI, value)
    assert is_telemetry_disabled_by_env()


def test_not_disabled_with_no_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    assert not is_telemetry_disabled_by_env()


# ---------- endpoint resolution ----------


def test_endpoint_defaults_to_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_ENDPOINT, raising=False)
    assert resolve_endpoint() == DEFAULT_ENDPOINT


def test_endpoint_overridable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ENDPOINT, "https://my-collector.example.com/v2/events")
    assert resolve_endpoint() == "https://my-collector.example.com/v2/events"


def test_endpoint_empty_string_means_no_send(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting endpoint=empty is the offline / air-gapped opt-out."""
    monkeypatch.setenv(ENV_ENDPOINT, "")
    assert resolve_endpoint() is None


# ---------- payload contract ----------


def test_payload_has_exact_fields() -> None:
    payload = make_payload(command="vm", install_id="abc-123")
    # CONTRACT: these are the ONLY fields ever sent.
    assert set(payload.keys()) == {"command", "cli_version", "os", "install_id"}


def test_payload_command_is_passed_through() -> None:
    assert make_payload(command="db", install_id="x")["command"] == "db"


def test_payload_includes_cli_version() -> None:
    assert make_payload(command="x", install_id="y")["cli_version"] == __version__


def test_payload_os_is_lowercased() -> None:
    with patch("platform.system", return_value="Linux"):
        assert make_payload(command="x", install_id="y")["os"] == "linux"
    with patch("platform.system", return_value="Darwin"):
        assert make_payload(command="x", install_id="y")["os"] == "darwin"
    with patch("platform.system", return_value="Windows"):
        assert make_payload(command="x", install_id="y")["os"] == "windows"


def test_payload_install_id_is_passed_through() -> None:
    assert make_payload(command="x", install_id="install-uuid")["install_id"] == "install-uuid"


def test_payload_does_not_leak_args_or_env() -> None:
    """Defence in depth: even if someone passes weird input, the payload
    keys are pinned. No timestamps, no hostnames, no PII."""
    payload = make_payload(command="vm list --status ACTIVE", install_id="x")
    # Even with arguments smuggled into command (caller shouldn't, but
    # defensive), payload only has the four documented fields.
    assert set(payload.keys()) == {"command", "cli_version", "os", "install_id"}
    forbidden = {"timestamp", "user", "email", "hostname", "ip", "args", "argv"}
    assert not forbidden.intersection(payload.keys())


# ---------- record_command behavior ----------


def test_record_command_no_op_when_disabled_by_env(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEVIRI_TELEMETRY=disable means no send AND no config writes."""
    monkeypatch.setenv(ENV_DISABLE, "disable")
    with patch("neviri_cli.utils.telemetry.send_async") as send:
        record_command("vm")
    send.assert_not_called()
    # Config wasn't touched
    cfg = load_config()
    assert cfg.telemetry is None
    assert cfg.install_id is None


def test_record_command_no_op_in_ci(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.setenv(ENV_CI, "true")
    with patch("neviri_cli.utils.telemetry.send_async") as send:
        record_command("vm")
    send.assert_not_called()


def test_record_command_no_op_when_telemetry_false(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If config says telemetry=false, no send even outside CI."""
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    cfg = load_config()
    cfg.telemetry = False
    save_config(cfg)

    with patch("neviri_cli.utils.telemetry.send_async") as send:
        record_command("vm")
    send.assert_not_called()


def test_record_command_skips_first_run_for_quiet_commands(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-run prompt must NOT fire on `neviri version`, `auth`, etc."""
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    with (
        patch("neviri_cli.utils.telemetry.prompt_user") as prompt,
        patch("neviri_cli.utils.telemetry.send_async") as send,
    ):
        record_command("version")
    prompt.assert_not_called()
    send.assert_not_called()


def test_record_command_skips_first_run_when_no_tty(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    with (
        patch("neviri_cli.utils.telemetry.is_interactive_tty", return_value=False),
        patch("neviri_cli.utils.telemetry.prompt_user") as prompt,
        patch("neviri_cli.utils.telemetry.send_async") as send,
    ):
        record_command("vm")
    prompt.assert_not_called()
    send.assert_not_called()


def test_record_command_prompts_and_persists_yes(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    with (
        patch("neviri_cli.utils.telemetry.is_interactive_tty", return_value=True),
        patch("neviri_cli.utils.telemetry.prompt_user", return_value=True),
        patch("neviri_cli.utils.telemetry.send_async") as send,
    ):
        record_command("vm")

    cfg = load_config()
    assert cfg.telemetry is True
    assert cfg.install_id is not None
    assert len(cfg.install_id) > 0
    send.assert_called_once()


def test_record_command_prompts_and_persists_no(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    with (
        patch("neviri_cli.utils.telemetry.is_interactive_tty", return_value=True),
        patch("neviri_cli.utils.telemetry.prompt_user", return_value=False),
        patch("neviri_cli.utils.telemetry.send_async") as send,
    ):
        record_command("vm")

    cfg = load_config()
    assert cfg.telemetry is False
    # install_id should NOT be generated when opting out
    assert cfg.install_id is None
    send.assert_not_called()


def test_record_command_uses_existing_install_id(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If telemetry=true and install_id is set, we use the existing one."""
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    cfg = load_config()
    cfg.telemetry = True
    cfg.install_id = "preexisting-install-id"
    save_config(cfg)

    captured: list[dict[str, object]] = []

    def capture(endpoint: str, payload: dict[str, object]) -> None:
        captured.append(payload)

    with patch("neviri_cli.utils.telemetry.send_async", side_effect=capture):
        record_command("vm")

    assert len(captured) == 1
    assert captured[0]["install_id"] == "preexisting-install-id"


def test_record_command_generates_install_id_if_missing(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """telemetry=true but install_id missing → generate one and persist."""
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    cfg = load_config()
    cfg.telemetry = True
    cfg.install_id = None
    save_config(cfg)

    with patch("neviri_cli.utils.telemetry.send_async"):
        record_command("vm")

    cfg2 = load_config()
    assert cfg2.install_id is not None


def test_record_command_skips_when_endpoint_empty(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEVIRI_TELEMETRY_ENDPOINT="" disables sending even when opted in."""
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    monkeypatch.setenv(ENV_ENDPOINT, "")
    cfg = load_config()
    cfg.telemetry = True
    cfg.install_id = "x"
    save_config(cfg)

    with patch("neviri_cli.utils.telemetry.send_async") as send:
        record_command("vm")
    send.assert_not_called()


def test_record_command_no_op_for_empty_command_name(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    cfg = load_config()
    cfg.telemetry = True
    cfg.install_id = "x"
    save_config(cfg)

    with patch("neviri_cli.utils.telemetry.send_async") as send:
        record_command(None)
        record_command("")
    send.assert_not_called()


def test_record_command_never_raises_on_network_error(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing HTTP call must not propagate up."""
    monkeypatch.delenv(ENV_DISABLE, raising=False)
    monkeypatch.delenv(ENV_CI, raising=False)
    cfg = load_config()
    cfg.telemetry = True
    cfg.install_id = "x"
    save_config(cfg)

    with patch(
        "neviri_cli.utils.telemetry.httpx.post",
        side_effect=httpx.ConnectError("no DNS"),
    ):
        # Call _post directly so the assertion isn't races against a daemon
        # thread that may not have run yet.
        from neviri_cli.utils.telemetry import _post

        _post("http://nowhere/v1", {"command": "vm"})  # no exception expected


# ---------- send_async fires daemon thread ----------


def test_send_async_uses_daemon_thread() -> None:
    """The spawned thread must be a daemon so it doesn't block CLI exit."""
    threads: list[object] = []
    real_thread = __import__("threading").Thread

    def capture_thread(*args: object, **kwargs: object) -> object:
        t = real_thread(*args, **kwargs)
        threads.append(t)
        # Prevent actual run
        t.start = lambda: None  # type: ignore[method-assign]
        return t

    with patch("neviri_cli.utils.telemetry.threading.Thread", side_effect=capture_thread):
        send_async("http://x", {"command": "vm"})

    assert len(threads) == 1
    assert getattr(threads[0], "daemon", False) is True


@respx.mock
def test_post_swallows_4xx_5xx_silently() -> None:
    """_post must NOT raise on HTTP error responses."""
    respx.post("https://t.test").mock(return_value=httpx.Response(500))
    from neviri_cli.utils.telemetry import _post

    _post("https://t.test", {"command": "vm"})  # no exception expected


# ---------- end-to-end via `neviri config` ----------


def test_neviri_config_set_telemetry_false_instantly_disables(
    isolated_home: Path,
    runner: object,
) -> None:
    """`neviri config set telemetry false` writes to config and the next
    record_command() must be a no-op."""
    from typer.testing import CliRunner

    from neviri_cli.app import app

    rn = CliRunner()
    result = rn.invoke(app, ["config", "set", "telemetry", "false"])
    assert result.exit_code == 0, result.stdout

    cfg = load_config()
    assert cfg.telemetry is False

    # And now the record path is a no-op
    import os as _os

    _os.environ.pop("NEVIRI_TELEMETRY", None)
    _os.environ.pop("CI", None)
    with patch("neviri_cli.utils.telemetry.send_async") as send:
        record_command("vm")
    send.assert_not_called()


def test_neviri_config_get_telemetry(isolated_home: Path) -> None:
    """`neviri config get telemetry` works (top-level CLIConfig key)."""
    from typer.testing import CliRunner

    from neviri_cli.app import app

    rn = CliRunner()
    rn.invoke(app, ["config", "set", "telemetry", "true"])
    result = rn.invoke(app, ["config", "get", "telemetry"])
    assert result.exit_code == 0
    assert "True" in result.stdout


# ---------- is_interactive_tty defensive behavior ----------


def test_is_interactive_tty_handles_missing_isatty() -> None:
    """If sys.stdin doesn't expose isatty (e.g. a captured stream), default
    to False rather than crashing."""
    fake_stdin = MagicMock()
    fake_stdin.isatty.side_effect = OSError("not a tty")
    with patch("sys.stdin", fake_stdin):
        assert not is_interactive_tty()
