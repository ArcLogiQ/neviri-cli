"""Tests for `neviri completion <shell>`.

We don't run the generated scripts in a real shell here — that's manual
verification (Story 13.2). What we verify automatically:

- Each supported shell produces non-empty output
- The output contains the program name and the expected completion env var
- An unsupported shell value is rejected at Typer's argument-validation layer
- Each shell's script has shape markers we recognise (function definition for
  bash/zsh, register-argcomplete invocation for fish, Register-ArgumentCompleter
  for powershell)
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.commands.completion import (
    COMPLETE_VAR,
    PROG_NAME,
    Shell,
    make_completion_script,
)
from neviri_cli.exceptions import UserError


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell", "pwsh"])
def test_make_completion_script_non_empty(shell: str) -> None:
    script = make_completion_script(shell)
    assert script, f"empty script for {shell}"
    assert PROG_NAME in script or COMPLETE_VAR in script


def test_make_completion_script_unsupported_raises_user_error() -> None:
    with pytest.raises(UserError) as info:
        make_completion_script("powershell-but-cool")
    assert "unsupported shell" in info.value.message


def test_bash_script_has_function_definition() -> None:
    script = make_completion_script("bash")
    # Typer's bash template defines a function whose name starts with _neviri
    # and registers it with `complete -F` (with various -o flags).
    assert "_neviri" in script
    assert "complete -" in script and "_neviri" in script


def test_zsh_script_has_compdef_directive() -> None:
    script = make_completion_script("zsh")
    assert "compdef" in script
    assert "_neviri" in script


def test_fish_script_uses_complete_command() -> None:
    script = make_completion_script("fish")
    # fish completion scripts use the `complete -c <cmd> -a '(...)'` pattern
    assert "complete" in script
    assert "neviri" in script


def test_powershell_script_registers_argument_completer() -> None:
    script = make_completion_script("powershell")
    # Typer's powershell template uses Register-ArgumentCompleter
    assert "Register-ArgumentCompleter" in script
    assert "neviri" in script


# ---------- CLI-level smoke tests ----------


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
def test_neviri_completion_command_emits_script(
    isolated_home: object,
    runner: CliRunner,
    shell: str,
) -> None:
    result = runner.invoke(app, ["completion", shell])
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip(), "expected non-empty script"


def test_neviri_completion_rejects_unknown_shell(isolated_home: object, runner: CliRunner) -> None:
    """Typer's enum argument validation kicks in before the command body runs."""
    result = runner.invoke(app, ["completion", "tcsh"])
    assert result.exit_code != 0


def test_shell_enum_lists_supported_values() -> None:
    """Pin the supported shells so a future hand can't silently drop one."""
    assert {s.value for s in Shell} == {"bash", "zsh", "fish", "powershell", "pwsh"}
