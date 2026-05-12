"""`neviri version` command.

Three modes:

- ``neviri version`` — print the installed version (alias for ``neviri --version``)
- ``neviri version --check`` — query GitHub Releases; tell the user if an upgrade is available
- ``neviri version --upgrade`` — download + swap in the latest binary (binary installs only)

The ``--upgrade`` flow exits the current process immediately on Windows so
the helper script can replace the locked .exe.
"""

from __future__ import annotations

from typing import Annotated

import typer

from neviri_cli import __version__
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error
from neviri_cli.utils.version_check import (
    fetch_latest_release,
    is_binary_install,
    is_newer,
    perform_self_update,
)


def version_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Check GitHub Releases for a newer version (network required).",
        ),
    ] = False,
    upgrade: Annotated[
        bool,
        typer.Option(
            "--upgrade",
            help="Download and swap in the latest release. Binary installs only.",
        ),
    ] = False,
) -> None:
    """Print the installed version. With --check, look up the latest release.
    With --upgrade, self-replace with the latest binary.

    Examples:

        neviri version
        neviri version --check
        neviri version --upgrade
    """
    if check and upgrade:
        handle_cli_error(
            type(
                "_E",
                (NeviriCLIError,),
                {"exit_code": 2},
            )("--check and --upgrade are mutually exclusive")
        )

    if not check and not upgrade:
        typer.echo(f"neviri {__version__}")
        return

    try:
        latest = fetch_latest_release()
    except NeviriCLIError as exc:
        handle_cli_error(exc)

    if check:
        if is_newer(latest.version, __version__):
            typer.echo(
                f"A newer version is available: {latest.version} "
                f"(you have {__version__}).\n"
                f"  Release notes: {latest.html_url}"
            )
            if is_binary_install():
                typer.echo("  Upgrade with: neviri version --upgrade")
            else:
                typer.echo("  Upgrade with: pip install --upgrade neviri-cli")
        else:
            typer.echo(f"neviri {__version__} is up to date.")
        return

    # upgrade path
    if not is_newer(latest.version, __version__):
        typer.echo(f"neviri {__version__} is already the latest release.")
        return

    try:
        target = perform_self_update(latest)
    except NeviriCLIError as exc:
        handle_cli_error(exc)

    typer.echo(
        f"Upgrading to {latest.version}. The replacement at {target} will be "
        "active on the next invocation."
    )
    # On Windows, the swap helper runs after we exit; on POSIX, the file is
    # already replaced. Either way, terminate now.
    raise typer.Exit(0)


__all__ = ["version_command"]
