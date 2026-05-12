"""Client factory: build a configured BaseClient from the active Typer context.

Pulls the active profile's ``api_url`` from the on-disk config, the active
token from the keyring/file/env priority chain, and constructs a
:class:`BaseClient` ready to use. Commands call this once at the top.
"""

from __future__ import annotations

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
    return BaseClient(base_url=profile.api_url, token=token, debug=obj.debug)
