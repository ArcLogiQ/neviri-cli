"""Typer root application for the Neviri CLI.

# Cold-start strategy (Phase 3 / Story 20)

This module is intentionally lean. The 14 subcommand groups (``vm``, ``db``,
``lb``, etc.) are **lazy-imported** via :class:`_LazyTyperGroup` — Click only
imports the module of the subcommand the user actually invoked.

That means ``neviri --version`` does not pay for ``httpx``, ``keyring``,
``rich.progress``, ``pydantic``, or any of the per-command client classes,
which would otherwise add 600-800ms to a cold start on Python 3.11+.

If you add a new subcommand group, register it in ``_LAZY_SUBCOMMANDS`` and
make sure the target module exposes a top-level ``*_app`` Typer instance.
"""

from __future__ import annotations

import importlib
from typing import Annotated, Any

import click
import typer
import typer.core

from neviri_cli import __version__
from neviri_cli.context import CLIContext
from neviri_cli.output import OutputFormat

# name -> "<module>:<attr>" pointing at a typer.Typer instance.
# Plain commands (not Typer groups) go in _LAZY_COMMANDS below.
_LAZY_SUBCOMMANDS: dict[str, str] = {
    "auth": "neviri_cli.commands.auth:auth_app",
    "config": "neviri_cli.commands.config:config_app",
    "vm": "neviri_cli.commands.vm:vm_app",
    "volume": "neviri_cli.commands.volume:volume_app",
    "network": "neviri_cli.commands.network:network_app",
    "subnet": "neviri_cli.commands.subnet:subnet_app",
    "floating-ip": "neviri_cli.commands.floating_ip:floating_ip_app",
    "db": "neviri_cli.commands.db:db_app",
    "object": "neviri_cli.commands.object_storage:object_app",
    "lb": "neviri_cli.commands.load_balancer:lb_app",
    "app": "neviri_cli.commands.app:app_app",
    "deploy": "neviri_cli.commands.deploy:deploy_app",
    "credit": "neviri_cli.commands.credit:credit_app",
    "payment": "neviri_cli.commands.payment:payment_app",
}

# name -> "<module>:<callable>" for single Typer commands.
_LAZY_COMMANDS: dict[str, str] = {
    "completion": "neviri_cli.commands.completion:completion_command",
    "version": "neviri_cli.commands.version:version_command",
}


class _LazyTyperGroup(typer.core.TyperGroup):
    """Click Group that resolves subcommand modules only when needed.

    Inherits Typer's group so help formatting + custom error handling are
    preserved.
    """

    def list_commands(self, ctx: click.Context) -> list[str]:
        eager = set(super().list_commands(ctx))
        return sorted(eager | set(_LAZY_SUBCOMMANDS) | set(_LAZY_COMMANDS))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        existing = super().get_command(ctx, cmd_name)
        if existing is not None:
            return existing
        spec = _LAZY_SUBCOMMANDS.get(cmd_name)
        if spec is not None:
            sub_app = _resolve(spec)
            return typer.main.get_command(sub_app)
        spec = _LAZY_COMMANDS.get(cmd_name)
        if spec is not None:
            return _command_from_callable(cmd_name, _resolve(spec))
        return None


def _resolve(spec: str) -> Any:
    modname, _, attr = spec.partition(":")
    module = importlib.import_module(modname)
    return getattr(module, attr)


def _command_from_callable(name: str, func: Any) -> click.Command:
    """Wrap a bare Typer command callable as a click.Command on demand.

    Mirrors what Typer does internally when you call ``app.command(name)(func)``
    — but deferred until the user actually asks for that command.

    The hidden ``_lazy_dummy`` forces Typer to emit a Group (with addressable
    ``.commands``) rather than a single TyperCommand.
    """
    tmp = typer.Typer(add_completion=False)
    tmp.command(name)(func)

    @tmp.command("_lazy_dummy", hidden=True)
    def _lazy_dummy() -> None:  # pragma: no cover - never invoked
        pass

    group = typer.main.get_command(tmp)
    assert isinstance(group, click.Group)
    cmd = group.commands[name]
    return cmd


app = typer.Typer(
    name="neviri",
    help="Official command-line interface for the Neviri Cloud Platform.",
    no_args_is_help=True,
    add_completion=False,
    cls=_LazyTyperGroup,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"neviri {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option(
            "--output",
            "-o",
            help="Output format for read commands.",
            case_sensitive=False,
        ),
    ] = "table",
    no_color: Annotated[
        bool,
        typer.Option(
            "--no-color",
            help="Disable ANSI color codes everywhere.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Print full stack traces and request/response dumps on error.",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="Named credentials profile from ~/.neviri/config.toml. "
            "Falls back to default_profile from the config when omitted.",
        ),
    ] = None,
) -> None:
    """Neviri CLI."""
    # Profile precedence: explicit --profile > config's default_profile > "default".
    # We load config eagerly so commands can rely on ctx.obj.profile being a real
    # profile name. Failure to load (e.g. corrupt TOML) intentionally bubbles up
    # so the user knows their config is broken.
    if profile is None:
        # Deferred import — config.py pulls in pydantic, which we want off the
        # `neviri --version` path. See module docstring.
        from neviri_cli.config import load_config

        cfg = load_config()
        resolved_profile = cfg.default_profile
    else:
        resolved_profile = profile

    ctx.obj = CLIContext(
        output=output,
        no_color=no_color,
        debug=debug,
        profile=resolved_profile,
    )

    # Opt-in telemetry. record_command never raises and never blocks.
    # Audit and policy: src/neviri_cli/utils/telemetry.py + docs/privacy.md.
    from neviri_cli.utils.telemetry import record_command

    record_command(ctx.invoked_subcommand)
