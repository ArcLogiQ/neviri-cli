"""Typed exception hierarchy for the Neviri CLI.

Exit-code contract (per architecture proposal section 4.6):

    0   success
    1   generic error
    2   user error (bad input, validation, missing flag)
    3   auth error (401/403, expired token, missing credentials)
    4   network error (connection refused, DNS, TLS, timeout)
    5   server error (backend 5xx)

These codes are part of the CLI's public contract: scripts and CI pipelines
rely on them. Changing them is a major-version bump.
"""

from __future__ import annotations

from typing import NoReturn


class NeviriCLIError(Exception):
    """Base for all CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.request_id = request_id


class UserError(NeviriCLIError):
    """The user's input was rejected before any backend call."""

    exit_code = 2


class AuthError(NeviriCLIError):
    """Authentication or authorization failure (401, 403, expired token)."""

    exit_code = 3


class NetworkError(NeviriCLIError):
    """Connection refused, DNS failure, TLS, or timeout."""

    exit_code = 4


class ServerError(NeviriCLIError):
    """Backend returned 5xx."""

    exit_code = 5


def handle_cli_error(exc: NeviriCLIError) -> NoReturn:
    """Print the error in a human form and exit with the typed code.

    Imports typer lazily so this module stays import-cheap and testable
    without pulling rich/typer into every test that just checks exit codes.
    """
    import typer

    suffix = f" (request-id: {exc.request_id})" if exc.request_id else ""
    typer.secho(f"Error: {exc.message}{suffix}", err=True, fg=typer.colors.RED)
    raise typer.Exit(exc.exit_code)
