"""Explicit IAM credentials, independent of the existing `neviri auth` flow."""

from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from neviri_cli.commands._common import emit, get_cli_ctx
from neviri_cli.config import ProfileConfig, get_profile, load_config, save_config
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error
from neviri_cli.iam import (
    IAM_ENV_KEY,
    IAM_ENV_SECRET,
    IAMCredentials,
    current_iam_identity,
    exchange_access_key,
    load_iam_credentials,
    login_console,
    logout_iam,
    require_iam_profile,
    save_iam_credentials,
    validate_iam_origin,
)
from neviri_cli.iam import (
    assume_role as issue_role_session,
)

iam_app = typer.Typer(
    name="iam", help="Use isolated IAM profiles and temporary sessions.", no_args_is_help=True
)


def _profile(ctx: typer.Context) -> tuple[str, ProfileConfig]:
    name = get_cli_ctx(ctx).profile
    profile = get_profile(load_config(), name)
    require_iam_profile(profile)
    return name, profile


@iam_app.command("configure")
def configure(
    ctx: typer.Context,
    iam_url: Annotated[str, typer.Option("--iam-url", help="IAM service origin.")],
    api_url: Annotated[str, typer.Option("--api-url", help="Business API origin.")],
    session_name: Annotated[str, typer.Option("--session-name")] = "cli",
) -> None:
    """Opt the selected profile into IAM. No legacy token is copied or removed."""
    try:
        name = get_cli_ctx(ctx).profile
        cfg = load_config()
        previous = get_profile(cfg, name)
        cfg.profiles[name] = ProfileConfig(
            auth_mode="iam",
            iam_url=validate_iam_origin(iam_url),
            api_url=validate_iam_origin(api_url),
            iam_session_name=session_name,
            output=previous.output,
        )
        save_config(cfg)
        typer.echo(f"Configured IAM profile '{name}'. Run `neviri --profile {name} iam login`.")
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@iam_app.command("login")
def login(
    ctx: typer.Context,
    access_key_id: Annotated[
        str | None, typer.Option("--access-key-id", help="Public NVIA key ID.")
    ] = None,
    secret_stdin: Annotated[
        bool, typer.Option("--secret-stdin", help="Read key secret from stdin instead of a prompt.")
    ] = False,
    username: Annotated[
        str | None, typer.Option("--username", help="IAM console username (password prompted).")
    ] = None,
    account_id: Annotated[int | None, typer.Option("--account-id", min=1)] = None,
    mfa: Annotated[
        bool, typer.Option("--mfa", help="Prompt for a six-digit authenticator code.")
    ] = False,
) -> None:
    """Sign in with an IAM access key, or an IAM username/password/MFA."""
    try:
        name, profile = _profile(ctx)
        debug = get_cli_ctx(ctx).debug
        if username is not None:
            if account_id is None or access_key_id is not None or secret_stdin:
                raise UserError(
                    "Console login requires --account-id and cannot include access-key options"
                )
            password = getpass.getpass("IAM password: ")
            code = getpass.getpass("Authenticator code: ") if mfa else None
            credentials = login_console(profile, account_id, username, password, code, debug=debug)
        else:
            if account_id is not None or mfa:
                raise UserError("--account-id and --mfa require --username")
            key = access_key_id or os.environ.get(IAM_ENV_KEY)
            if not key:
                raise UserError("Pass --access-key-id or set NEVIRI_IAM_ACCESS_KEY_ID")
            secret = (
                sys.stdin.readline().strip()
                if secret_stdin
                else os.environ.get(IAM_ENV_SECRET) or getpass.getpass("IAM secret access key: ")
            )
            if not secret:
                raise UserError("IAM secret access key cannot be empty")
            credentials = exchange_access_key(
                profile, IAMCredentials(access_key_id=key, secret_access_key=secret), debug=debug
            )
        if profile.iam_role_arn:
            credentials = issue_role_session(profile, credentials, debug=debug)
        save_iam_credentials(name, credentials)
        typer.echo(
            f"Signed in to IAM as {credentials.principal_arn} "
            f"(profile: {name}, expires: {credentials.expires_at})."
        )
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@iam_app.command("assume-role")
def assume_role(
    ctx: typer.Context,
    role_arn: str,
    session_name: Annotated[str, typer.Option("--session-name")] = "cli-role",
    duration: Annotated[int, typer.Option("--duration", min=900, max=43200)] = 900,
    external_id: Annotated[str | None, typer.Option("--external-id")] = None,
    session_policy: Annotated[
        Path | None, typer.Option("--session-policy", exists=True, dir_okay=False)
    ] = None,
) -> None:
    """Assume a role; preserve the source access key for later expiry refresh."""
    try:
        name, profile = _profile(ctx)
        document = None
        if session_policy:
            try:
                document = json.loads(session_policy.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise UserError("Session policy must be a readable JSON document") from exc
            if not isinstance(document, dict) or not isinstance(document.get("Statement"), list):
                raise UserError("Session policy requires a Statement array")
        profile = profile.model_copy(
            update={
                "iam_role_arn": role_arn,
                "iam_session_name": session_name,
                "iam_duration_seconds": duration,
                "iam_external_id": external_id,
                "iam_session_policy": document,
            }
        )
        source = load_iam_credentials(name)
        if source.access_key_id and source.secret_access_key:
            # A previous role token cannot be chained; exchange the user key.
            source = exchange_access_key(profile, source, debug=get_cli_ctx(ctx).debug)
        issued = issue_role_session(profile, source, debug=get_cli_ctx(ctx).debug)
        save_iam_credentials(name, issued)
        cfg = load_config()
        cfg.profiles[name] = profile
        save_config(cfg)
        typer.echo(f"Assumed {issued.principal_arn} (expires: {issued.expires_at}).")
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@iam_app.command("whoami")
def whoami(ctx: typer.Context) -> None:
    """Read current identity from the IAM service; no unsigned identity cache."""
    try:
        name, profile = _profile(ctx)
        emit(ctx, current_iam_identity(name, profile, debug=get_cli_ctx(ctx).debug))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@iam_app.command("logout")
def logout(ctx: typer.Context) -> None:
    """Revoke the stored IAM session and clear only its isolated credentials."""
    try:
        name, profile = _profile(ctx)
        revoked = logout_iam(name, profile, debug=get_cli_ctx(ctx).debug)
        typer.echo(
            f"Cleared IAM credentials for '{name}'."
            + (
                ""
                if revoked
                else " Server revocation was not confirmed; the service is unavailable."
            )
        )
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@iam_app.command("operation-status")
def operation_status(ctx: typer.Context, operation_id: str) -> None:
    """Read a persisted server operation using its separate IAM permission."""
    try:
        from neviri_cli.iam_operations import get_operation

        name, profile = _profile(ctx)
        emit(ctx, get_operation(name, profile, operation_id, debug=get_cli_ctx(ctx).debug))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
