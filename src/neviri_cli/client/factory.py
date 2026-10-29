"""Client factory: build a configured BaseClient from the active Typer context.

Pulls the active profile's ``api_url`` from the on-disk config, the active
token from the keyring/file/env priority chain, and constructs a
:class:`BaseClient` ready to use. Commands call this once at the top.
"""

from __future__ import annotations

import os

import typer

from neviri_cli.auth import get_active_token
from neviri_cli.client.base import BaseClient
from neviri_cli.config import get_profile, load_config
from neviri_cli.context import CLIContext
from neviri_cli.exceptions import AuthError


def make_client(ctx: typer.Context) -> BaseClient:
    """Build a :class:`BaseClient` for the active profile.

    Raises :class:`AuthError` if no token is available - commands handle that
    via :func:`neviri_cli.exceptions.handle_cli_error`.
    """
    obj = ctx.obj
    assert isinstance(obj, CLIContext)
    cfg = load_config()
    profile = get_profile(cfg, obj.profile)
    token = get_active_token(obj.profile)
    if not token:
        raise AuthError(
            f"Not logged in (profile: {obj.profile}). "
            "Run `neviri auth login` or set $NEVIRI_API_TOKEN."
        )
    if token.startswith("nvk_"):
        project_id = os.environ.get("NEVIRI_PROJECT_ID", profile.project_id)
        environment = os.environ.get("NEVIRI_ENVIRONMENT", profile.environment)
        if not project_id or not environment:
            raise AuthError(
                "Management credentials require project_id and environment in the profile "
                "or NEVIRI_PROJECT_ID and NEVIRI_ENVIRONMENT."
            )
        if any(character in project_id + environment for character in "\r\n"):
            raise AuthError("Invalid management credential bindings.")
        if not profile.api_url.startswith("https://"):
            raise AuthError("Management credentials require an HTTPS API URL.")
        # Ambiguous writes must be reconciled, never replayed automatically.
        return BaseClient(
            base_url=profile.api_url,
            token=token,
            debug=obj.debug,
            project_id=project_id,
            environment=environment,
            max_retries=0,
        )
    return BaseClient(base_url=profile.api_url, token=token, debug=obj.debug)
