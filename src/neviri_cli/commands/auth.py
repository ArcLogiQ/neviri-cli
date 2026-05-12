"""`neviri auth` subcommands: login / logout / whoami / token."""

from __future__ import annotations

import getpass
import os
import sys
from typing import Annotated

import typer

from neviri_cli.auth import (
    ENV_TOKEN,
    clear_token,
    decode_jwt_payload_unsafe,
    get_active_token,
    is_api_token,
    login_with_password,
    store_token,
)
from neviri_cli.config import get_profile, load_config, save_config
from neviri_cli.context import CLIContext
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error

auth_app = typer.Typer(
    name="auth",
    help="Manage authentication and tokens.",
    no_args_is_help=True,
)


def _ctx(ctx: typer.Context) -> CLIContext:
    obj = ctx.obj
    assert isinstance(obj, CLIContext)
    return obj


@auth_app.command("login")
def login(
    ctx: typer.Context,
    email: Annotated[
        str | None,
        typer.Option("--email", "-e", help="Email for password-based login. Prompted if omitted."),
    ] = None,
    api_token: Annotated[
        str | None,
        typer.Option(
            "--api-token",
            help=(
                "Use a long-lived API token instead of email/password. Pass `-` to read from stdin."
            ),
        ),
    ] = None,
) -> None:
    """Log in. Either email/password or `--api-token`.

    Examples:

        neviri auth login
        neviri auth login --email alice@example.com
        neviri auth login --api-token nvr_xxx...
        echo "$TOKEN" | neviri auth login --api-token -
    """
    cli_ctx = _ctx(ctx)
    profile_name = cli_ctx.profile

    try:
        if api_token is not None:
            if api_token == "-":  # nosec B105 - stdin sentinel, not a credential
                api_token = sys.stdin.readline().strip()
            if not api_token:
                raise UserError("API token cannot be empty")
            if not is_api_token(api_token):
                raise UserError("API token must start with 'nvr_'")
            store_token(profile_name, api_token)
            typer.echo(f"Stored API token for profile '{profile_name}'.")
            return

        # Password flow
        if email is None:
            email = typer.prompt("Email")
        password = getpass.getpass("Password: ")

        cfg = load_config()
        profile = get_profile(cfg, profile_name)

        response = login_with_password(profile.auth_url, email, password)
        token = response.get("token")
        if not isinstance(token, str):
            raise NeviriCLIError("login response did not include an access token")

        store_token(profile_name, token)

        # Cache identity for whoami without re-decoding next time.
        user = response.get("user") or {}
        profile.email = user.get("email") or email
        profile.user_id = user.get("id")
        profile.name = user.get("name")

        payload = decode_jwt_payload_unsafe(token)
        if payload:
            account_id = payload.get("accountId")
            if isinstance(account_id, int):
                profile.account_id = account_id

        cfg.profiles[profile_name] = profile
        save_config(cfg)

        typer.echo(f"Logged in as {profile.email} (profile: {profile_name})")
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@auth_app.command("logout")
def logout(ctx: typer.Context) -> None:
    """Clear stored credentials for the active profile."""
    cli_ctx = _ctx(ctx)
    clear_token(cli_ctx.profile)
    typer.echo(f"Logged out of profile '{cli_ctx.profile}'.")


@auth_app.command("whoami")
def whoami(ctx: typer.Context) -> None:
    """Print the current identity and active profile."""
    cli_ctx = _ctx(ctx)
    profile_name = cli_ctx.profile

    if os.environ.get(ENV_TOKEN):
        typer.echo(f"Authenticated via {ENV_TOKEN} env var (profile: {profile_name})")
        return

    token = get_active_token(profile_name)
    if not token:
        typer.echo(f"Not logged in (profile: {profile_name})", err=True)
        raise typer.Exit(3)

    if is_api_token(token):
        typer.echo(f"Authenticated via API token (profile: {profile_name})")
        return

    cfg = load_config()
    profile = get_profile(cfg, profile_name)
    if profile.email:
        account_str = f", account: {profile.account_id}" if profile.account_id else ""
        typer.echo(f"{profile.email} (profile: {profile_name}{account_str})")
        return

    payload = decode_jwt_payload_unsafe(token)
    if payload and payload.get("email"):
        typer.echo(f"{payload['email']} (profile: {profile_name})")
    else:
        typer.echo(f"Authenticated (profile: {profile_name})")


@auth_app.command("token")
def show_token(ctx: typer.Context) -> None:
    """Print the active token to stdout (for scripting; handle with care)."""
    cli_ctx = _ctx(ctx)
    token = get_active_token(cli_ctx.profile)
    if not token:
        typer.echo(f"Not logged in (profile: {cli_ctx.profile})", err=True)
        raise typer.Exit(3)
    typer.echo(token)
