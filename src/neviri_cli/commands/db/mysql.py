"""`neviri db mysql` subcommands. Wraps `/api/v1/mysql/*` plus the shared
backup/restore endpoints."""

from __future__ import annotations

from neviri_cli.client.database import MysqlClient
from neviri_cli.commands.db._engine import EngineSpec, build_engine_app

mysql_app = build_engine_app(
    EngineSpec(
        name="mysql",
        display="MySQL",
        backend_type="mysql",
        default_flavor="SMALL",
        user_field="mysql_user",
        pass_field="mysql_pass",  # nosec B106 - JSON field name from API, not a password value
        has_region=True,
        has_flavors_endpoint=True,
        has_lts_version=False,
        client_factory=MysqlClient,
    )
)
