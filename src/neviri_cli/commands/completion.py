"""`neviri completion <shell>` - emit a shell-completion script.

Wraps Click's :mod:`click.shell_completion` machinery (which Typer extends to
register PowerShell variants). The user runs this once and pipes the output
into their shell's startup file. See ``docs/getting-started.md`` for install
snippets.

Why this is a discrete command instead of Typer's built-in
``--install-completion`` / ``--show-completion`` flags: matching the proposal
section 4.5 surface (``neviri completion bash``), and giving users a stable
command they can hardcode in dotfiles without depending on Typer flag names.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer
import typer.main

# Typer ships its own PowerShell + zsh + fish + bash completion classes but
# only registers them with Click when its CLI entry point runs (when the user
# invoked the program via `python -m typer ...`). When *we* generate the
# script directly, we need to trigger that registration ourselves. Internal
# API but stable across typer >=0.12 — verified against typer 0.25.
from typer._completion_classes import completion_init

completion_init()

from click.shell_completion import get_completion_class  # noqa: E402

from neviri_cli.exceptions import UserError, handle_cli_error  # noqa: E402

PROG_NAME = "neviri"
COMPLETE_VAR = "_NEVIRI_COMPLETE"


class Shell(StrEnum):
    bash = "bash"
    zsh = "zsh"
    fish = "fish"
    powershell = "powershell"
    pwsh = "pwsh"


def make_completion_script(shell: str) -> str:
    """Return the completion script for ``shell``.

    Raises :class:`UserError` if the shell isn't supported by the installed
    Click + Typer versions.
    """
    cls = get_completion_class(shell)
    if cls is None:
        raise UserError(
            f"unsupported shell {shell!r}. Supported: bash, zsh, fish, powershell, pwsh."
        )

    # Lazy import to avoid a circular dependency with neviri_cli.app.
    from neviri_cli.app import app as typer_app

    click_command = typer.main.get_command(typer_app)
    comp = cls(
        cli=click_command,
        ctx_args={},
        prog_name=PROG_NAME,
        complete_var=COMPLETE_VAR,
    )
    return str(comp.source())


def completion_command(
    ctx: typer.Context,
    shell: Annotated[
        Shell,
        typer.Argument(help="Shell to generate the completion script for."),
    ],
) -> None:
    """Print a shell-completion script.

    Pipe the output into your shell's config to enable completion.

    Examples:

        # bash (one-time, current session):
        eval "$(neviri completion bash)"

        # zsh (persistent):
        neviri completion zsh >> ~/.zshrc

        # fish:
        neviri completion fish > ~/.config/fish/completions/neviri.fish

        # PowerShell (persistent):
        neviri completion powershell | Out-String >> $PROFILE
    """
    del ctx
    try:
        typer.echo(make_completion_script(shell.value))
    except UserError as exc:  # pragma: no cover - Typer's enum validation
        # blocks unknown shells before reaching this line; the catch is here
        # so the unsupported-shell helper text still surfaces sensibly if
        # Click's completion class registry ever desyncs.
        handle_cli_error(exc)


__all__ = ["COMPLETE_VAR", "PROG_NAME", "Shell", "completion_command", "make_completion_script"]
