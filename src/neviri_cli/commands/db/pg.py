"""`neviri db pg` subcommands. Wraps `/api/v1/postgres/*` plus the shared
backup/restore endpoints."""

from __future__ import annotations

from neviri_cli.client.database import PostgresClient
from neviri_cli.commands.db._engine import EngineSpec, build_engine_app

pg_app = build_engine_app(
    EngineSpec(
        name="pg",
        display="PostgreSQL",
        backend_type="postgresql",
        default_flavor="SMALL",
        user_field="postgres_user",
        pass_field="postgres_pass",  # nosec B106 - JSON field name from API, not a password value
        has_region=True,
        has_flavors_endpoint=True,
        has_lts_version=False,
        client_factory=PostgresClient,
    )
)
