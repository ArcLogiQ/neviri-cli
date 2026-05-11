"""`neviri db mongo` subcommands. Wraps `/api/v1/database/*` plus the shared
backup/restore endpoints."""

from __future__ import annotations

from neviri_cli.client.database import MongoClient
from neviri_cli.commands.db._engine import EngineSpec, build_engine_app

mongo_app = build_engine_app(
    EngineSpec(
        name="mongo",
        display="MongoDB",
        backend_type="mongodb",
        default_flavor="M10",
        user_field="mongo_user",
        pass_field="mongo_pass",
        has_region=False,
        # The MongoDB router does not expose `GET /flavors` — clients use the
        # platform docs / web UI to pick a tier.
        has_flavors_endpoint=False,
        has_lts_version=True,
        client_factory=MongoClient,
    )
)
