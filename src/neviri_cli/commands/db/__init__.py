"""`neviri db` parent app — wires MySQL, PostgreSQL, MongoDB subgroups."""

from __future__ import annotations

import typer

from neviri_cli.commands.db.mongo import mongo_app
from neviri_cli.commands.db.mysql import mysql_app
from neviri_cli.commands.db.pg import pg_app

db_app = typer.Typer(
    name="db",
    help="Manage managed databases (MongoDB, MySQL, PostgreSQL).",
    no_args_is_help=True,
)

db_app.add_typer(mysql_app, name="mysql")
db_app.add_typer(pg_app, name="pg")
db_app.add_typer(mongo_app, name="mongo")

__all__ = ["db_app"]
