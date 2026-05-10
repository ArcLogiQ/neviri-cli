"""`neviri config` subcommands: get / set / list / use-context."""

from __future__ import annotations

import types
import typing

import typer

from neviri_cli.config import ProfileConfig, get_profile, load_config, save_config
from neviri_cli.context import CLIContext

config_app = typer.Typer(
    name="config",
    help="Manage CLI configuration profiles.",
    no_args_is_help=True,
)


def _ctx(ctx: typer.Context) -> CLIContext:
    obj = ctx.obj
    assert isinstance(obj, CLIContext)
    return obj


def _is_int_annotation(annotation: object) -> bool:
    """True for `int` and any union containing `int` (e.g. `int | None`)."""
    if annotation is int:
        return True
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation) is typing.Union:
        return int in typing.get_args(annotation)
    return False


def _coerce_value(key: str, raw: str) -> object:
    """Convert a string CLI input to the right type for the field."""
    field = ProfileConfig.model_fields.get(key)
    if field is None:
        raise typer.BadParameter(f"unknown config key: {key}")
    if _is_int_annotation(field.annotation):
        try:
            return int(raw)
        except ValueError as exc:
            raise typer.BadParameter(f"{key} must be an integer") from exc
    return raw


@config_app.command("get")
def get_value(ctx: typer.Context, key: str) -> None:
    """Print a config value for the active profile.

    Example:

        neviri config get api_url
    """
    cli_ctx = _ctx(ctx)
    cfg = load_config()
    profile = get_profile(cfg, cli_ctx.profile)
    if key not in ProfileConfig.model_fields:
        typer.echo(f"Unknown config key: {key}", err=True)
        raise typer.Exit(2)
    value = getattr(profile, key)
    typer.echo("" if value is None else str(value))


@config_app.command("set")
def set_value(ctx: typer.Context, key: str, value: str) -> None:
    """Set a config value for the active profile.

    Example:

        neviri config set api_url https://api.neviri.com
    """
    cli_ctx = _ctx(ctx)
    cfg = load_config()
    profile = get_profile(cfg, cli_ctx.profile)
    if key not in ProfileConfig.model_fields:
        typer.echo(f"Unknown config key: {key}", err=True)
        raise typer.Exit(2)
    coerced = _coerce_value(key, value)
    setattr(profile, key, coerced)
    cfg.profiles[cli_ctx.profile] = profile
    save_config(cfg)
    typer.echo(f"{key} = {coerced}")


@config_app.command("list")
def list_config(ctx: typer.Context) -> None:
    """List all profiles and their settings."""
    del ctx  # active profile not relevant for "list" — show everything
    cfg = load_config()
    typer.echo(f"default_profile = {cfg.default_profile}")
    for name, profile in cfg.profiles.items():
        typer.echo(f"\n[{name}]")
        for k, v in profile.model_dump(exclude_none=True).items():
            typer.echo(f"  {k} = {v}")


@config_app.command("use-context")
def use_context(ctx: typer.Context, profile: str) -> None:
    """Set the default profile for subsequent invocations.

    Example:

        neviri config use-context staging
    """
    del ctx
    cfg = load_config()
    if profile not in cfg.profiles:
        cfg.profiles[profile] = ProfileConfig()
    cfg.default_profile = profile
    save_config(cfg)
    typer.echo(f"Default profile set to '{profile}'")
