"""Typer root application for the Neviri CLI."""

from __future__ import annotations

from typing import Annotated

import typer

from neviri_cli import __version__
from neviri_cli.commands.app import app_app
from neviri_cli.commands.auth import auth_app
from neviri_cli.commands.config import config_app
from neviri_cli.commands.db import db_app
from neviri_cli.commands.deploy import deploy_app
from neviri_cli.commands.floating_ip import floating_ip_app
from neviri_cli.commands.load_balancer import lb_app
from neviri_cli.commands.network import network_app
from neviri_cli.commands.object_storage import object_app
from neviri_cli.commands.subnet import subnet_app
from neviri_cli.commands.vm import vm_app
from neviri_cli.commands.volume import volume_app
from neviri_cli.config import load_config
from neviri_cli.context import CLIContext
from neviri_cli.output import OutputFormat

app = typer.Typer(
    name="neviri",
    help="Official command-line interface for the Neviri Cloud Platform.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")
app.add_typer(vm_app, name="vm")
app.add_typer(volume_app, name="volume")
app.add_typer(network_app, name="network")
app.add_typer(subnet_app, name="subnet")
app.add_typer(floating_ip_app, name="floating-ip")
app.add_typer(db_app, name="db")
app.add_typer(object_app, name="object")
app.add_typer(lb_app, name="lb")
app.add_typer(app_app, name="app")
app.add_typer(deploy_app, name="deploy")


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
