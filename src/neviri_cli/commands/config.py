"""`neviri config` subcommands: get / set / list / use-context.

Most config keys live on the active profile (api_url, auth_url, etc.).
A small number are account-wide (top-level CLIConfig): currently
``telemetry`` and ``install_id``. Those are handled specially in get / set
so users can run ``neviri config set telemetry false`` without thinking
about per-profile vs account-wide.
"""

from __future__ import annotations

import types
import typing

import typer

from neviri_cli.config import CLIConfig, ProfileConfig, get_profile, load_config, save_config
from neviri_cli.context import CLIContext

config_app = typer.Typer(
    name="config",
    help="Manage CLI configuration profiles.",
    no_args_is_help=True,
)

# Keys that live on CLIConfig (account-wide), not on ProfileConfig.
_TOP_LEVEL_KEYS = {"telemetry", "install_id", "default_profile"}


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


def _is_bool_annotation(annotation: object) -> bool:
    """True for `bool` and any union containing `bool` (e.g. `bool | None`)."""
    if annotation is bool:
        return True
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation) is typing.Union:
        return bool in typing.get_args(annotation)
    return False


def _coerce_value(annotation: object, key: str, raw: str) -> object:
    """Convert a string CLI input to the field's annotated type."""
    # bool BEFORE int because `bool` is a subclass of `int` in Python.
    if _is_bool_annotation(annotation):
        lowered = raw.strip().lower()
        if lowered in ("true", "1", "yes", "y", "on"):
            return True
        if lowered in ("false", "0", "no", "n", "off"):
            return False
        raise typer.BadParameter(f"{key} must be a boolean (true/false)")
    if _is_int_annotation(annotation):
        try:
            return int(raw)
        except ValueError as exc:
            raise typer.BadParameter(f"{key} must be an integer") from exc
    return raw


def _field_annotation(key: str) -> object | None:
    """Resolve the annotated type for either a top-level or profile key."""
    if key in CLIConfig.model_fields:
        return CLIConfig.model_fields[key].annotation
    if key in ProfileConfig.model_fields:
        return ProfileConfig.model_fields[key].annotation
    return None


@config_app.command("get")
def get_value(ctx: typer.Context, key: str) -> None:
    """Print a config value.

    Top-level keys (telemetry, install_id, default_profile) come from
    CLIConfig; everything else from the active profile.

    Example:

        neviri config get api_url
        neviri config get telemetry
    """
    cli_ctx = _ctx(ctx)
    cfg = load_config()

    if key in _TOP_LEVEL_KEYS:
        value = getattr(cfg, key)
    elif key in ProfileConfig.model_fields:
        profile = get_profile(cfg, cli_ctx.profile)
        value = getattr(profile, key)
    else:
        typer.echo(f"Unknown config key: {key}", err=True)
        raise typer.Exit(2)

    typer.echo("" if value is None else str(value))


@config_app.command("set")
def set_value(ctx: typer.Context, key: str, value: str) -> None:
    """Set a config value.

    Examples:

        neviri config set api_url https://api.neviri.com
        neviri config set telemetry false
    """
    cli_ctx = _ctx(ctx)
    cfg = load_config()
    annotation = _field_annotation(key)
    if annotation is None:
        typer.echo(f"Unknown config key: {key}", err=True)
        raise typer.Exit(2)

    coerced = _coerce_value(annotation, key, value)

    if key in _TOP_LEVEL_KEYS:
        setattr(cfg, key, coerced)
    else:
        profile = get_profile(cfg, cli_ctx.profile)
        setattr(profile, key, coerced)
        cfg.profiles[cli_ctx.profile] = profile

    save_config(cfg)
    typer.echo(f"{key} = {coerced}")


@config_app.command("list")
def list_config(ctx: typer.Context) -> None:
    """List all profiles and their settings, plus account-wide config."""
    del ctx
    cfg = load_config()
    typer.echo(f"default_profile = {cfg.default_profile}")
    if cfg.telemetry is not None:
        typer.echo(f"telemetry = {cfg.telemetry}")
    if cfg.install_id is not None:
        typer.echo(f"install_id = {cfg.install_id}")
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
