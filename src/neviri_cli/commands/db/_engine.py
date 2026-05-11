"""Generic engine command builder.

Each of MySQL / PostgreSQL / MongoDB exposes the same shape of commands
(`list`, `get`, `status`, `create`, `delete`, `scale`, `flavors`, `backup`,
`backups`, `restore`, `restore-status`). Only the URL prefix, default
flavor, password field name, and a few presence flags differ.

This module exposes :func:`build_engine_app` which returns a fully wired
:class:`typer.Typer` for one engine. The per-engine modules
(``commands/db/mysql.py`` etc.) are 10-line shims that call this with an
:class:`EngineSpec`.
"""

from __future__ import annotations

import getpass
import sys
from dataclasses import dataclass
from typing import Annotated, Any

import typer

from neviri_cli.client.backup import BackupClient
from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error


@dataclass(frozen=True)
class EngineSpec:
    """Describes the differences between MySQL / PG / Mongo for the engine
    command builder."""

    name: str
    """``mysql`` / ``pg`` / ``mongo`` - used in help text and as the engine identifier."""

    display: str
    """Pretty name for help text (``MySQL``, ``PostgreSQL``, ``MongoDB``)."""

    backend_type: str
    """The ``database_type`` field value the backend's backup endpoint expects
    (``mysql``, ``postgresql``, ``mongodb``)."""

    default_flavor: str
    user_field: str
    pass_field: str
    has_region: bool
    has_flavors_endpoint: bool
    has_lts_version: bool
    """MongoDB takes ``mongo_lts_version``; MySQL/PG do not."""

    client_factory: Any
    """Callable: ``BaseClient -> EngineClient``. Each EngineClient has the same
    method names (list_databases, create_database, ...)."""


def _read_password(*, password_stdin: bool, prompt: str) -> str:
    """Read a sensitive password from stdin or via getpass prompt.

    Never accept passwords as plain CLI args (they leak to shell history).
    """
    if password_stdin:
        pw = sys.stdin.readline().rstrip("\n")
        if not pw:
            raise UserError("password from stdin was empty")
        return pw
    if not sys.stdin.isatty():
        raise UserError("no TTY available; pass --password-stdin and pipe the password to stdin")
    pw = getpass.getpass(prompt)
    if not pw:
        raise UserError("password cannot be empty")
    return pw


def build_engine_app(spec: EngineSpec) -> typer.Typer:
    app = typer.Typer(
        name=spec.name,
        help=f"Manage {spec.display} clusters.",
        no_args_is_help=True,
    )

    def _client(ctx: typer.Context) -> Any:
        return spec.client_factory(make_client(ctx))

    def _backup_client(ctx: typer.Context) -> BackupClient:
        return BackupClient(make_client(ctx))

    # ---------- read commands ----------

    @app.command("list")
    def list_databases(ctx: typer.Context) -> None:
        """List clusters for the active account."""
        try:
            emit(ctx, _client(ctx).list_databases())
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    @app.command("get")
    def get_database(
        ctx: typer.Context,
        database_id: Annotated[int, typer.Argument(help="Cluster ID.")],
    ) -> None:
        """Show full details for a cluster.

        The backend has no per-engine ``GET /<id>`` endpoint, so this command
        lists all clusters and filters by ID client-side.
        """
        try:
            for row in _client(ctx).list_databases():
                if row.get("id") == database_id:
                    emit(ctx, row)
                    return
            raise UserError(f"no {spec.display} cluster with id {database_id}")
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    @app.command("status")
    def get_status(
        ctx: typer.Context,
        database_id: Annotated[int, typer.Argument(help="Cluster ID.")],
    ) -> None:
        """Print a cluster's current status (lighter than `get`)."""
        try:
            emit(ctx, _client(ctx).get_status(database_id))
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    if spec.has_flavors_endpoint:

        @app.command("flavors")
        def list_flavors(ctx: typer.Context) -> None:
            """List available flavors (instance plans) for this engine."""
            try:
                result = _client(ctx).list_flavors()
                flavors = result.get("flavors", result)
                emit(ctx, flavors)
            except NeviriCLIError as exc:
                handle_cli_error(exc)

    # ---------- create ----------

    region_doc = " --region central_india" if spec.has_region else ""
    lts_doc = " --lts-version 7.0" if spec.has_lts_version else ""
    _create_help = (
        f"Provision a new {spec.display} cluster.\n\n"
        f"Example: neviri db {spec.name} create my-cluster "
        f"--flavor {spec.default_flavor}{region_doc}{lts_doc}"
    )

    @app.command("create", help=_create_help)
    def create_database(
        ctx: typer.Context,
        name: Annotated[str, typer.Argument(help="Cluster name.")],
        flavor: Annotated[
            str, typer.Option("--flavor", "-f", help="Instance plan / flavor.")
        ] = spec.default_flavor,
        db_name: Annotated[str, typer.Option("--db-name", help="Initial database name.")] = "",
        replicas: Annotated[int, typer.Option("--replicas", help="Replica count.", min=1)] = 3,
        user: Annotated[str, typer.Option("--user", "-u", help="Initial DB admin username.")] = "",
        region: Annotated[
            str | None,
            typer.Option("--region", "-r", help="Region to provision in."),
        ] = ("central_india" if spec.has_region else None),
        lts_version: Annotated[
            str | None,
            typer.Option("--lts-version", help="MongoDB LTS version (Mongo only)."),
        ] = None,
        password_stdin: Annotated[
            bool,
            typer.Option(
                "--password-stdin",
                help="Read the DB user password from stdin instead of prompting.",
            ),
        ] = False,
    ) -> None:
        try:
            password = _read_password(
                password_stdin=password_stdin,
                prompt=f"{spec.display} admin password: ",
            )

            body: dict[str, Any] = {
                "name": name,
                "flavor": flavor,
                "db_name": db_name,
                "replicas": replicas,
                spec.user_field: user,
                spec.pass_field: password,
            }
            if spec.has_region and region:
                body["region"] = region
            if spec.has_lts_version and lts_version:
                body["mongo_lts_version"] = lts_version

            emit(ctx, _client(ctx).create_database(body))
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    # ---------- delete ----------

    @app.command(
        "delete",
        help=f"Delete a {spec.display} cluster (irreversible).",
    )
    def delete_database(
        ctx: typer.Context,
        database_id: Annotated[int, typer.Argument(help="Cluster ID.")],
        yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    ) -> None:
        confirm_or_exit(
            f"Delete {spec.display} cluster {database_id}? All data on the cluster will be lost.",
            yes=yes,
        )
        try:
            emit(ctx, _client(ctx).delete_database(database_id))
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    # ---------- scale ----------

    @app.command("scale")
    def scale_database(
        ctx: typer.Context,
        database_id: Annotated[int, typer.Argument(help="Cluster ID.")],
        flavor: Annotated[str, typer.Option("--flavor", "-f", help="Target flavor / plan.")],
        storage: Annotated[
            int | None,
            typer.Option("--storage", help="Storage size in GB."),
        ] = None,
        yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    ) -> None:
        """Scale a cluster to a new flavor. May cause brief downtime."""
        confirm_or_exit(
            f"Scale {spec.display} cluster {database_id} to '{flavor}'? "
            "This will cause a brief downtime.",
            yes=yes,
        )
        body: dict[str, Any] = {"flavor": flavor}
        if spec.name == "mongo":
            # Backend's ScaleDatabaseRequest expects `type` field for the
            # unified scale endpoint to dispatch correctly.
            body["type"] = "mongodb"
        if storage is not None:
            body["storage"] = storage
        try:
            emit(ctx, _client(ctx).scale_database(database_id, body))
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    # ---------- backup ----------

    _backup_help = (
        f"Trigger a backup of a {spec.display} cluster.\n\n"
        "Note: the backend has no job-id or progress endpoint, so this returns "
        f"immediately. Run `neviri db {spec.name} backups --cluster <name>` to "
        "see when the backup completes. Progress streaming is on the Phase 3 roadmap."
    )

    @app.command("backup", help=_backup_help)
    def create_backup(
        ctx: typer.Context,
        cluster_name: Annotated[str, typer.Argument(help="Cluster name (not ID).")],
    ) -> None:
        try:
            emit(
                ctx,
                _backup_client(ctx).create_backup(
                    cluster_name=cluster_name, database_type=spec.backend_type
                ),
            )
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    @app.command("backups")
    def list_backups(
        ctx: typer.Context,
        cluster_name: Annotated[
            str | None,
            typer.Option("--cluster", "-c", help="Filter by cluster name."),
        ] = None,
    ) -> None:
        """List backups (optionally filtered to one cluster)."""
        try:
            response = _backup_client(ctx).list_backups(cluster_name=cluster_name)
            # backend envelope: {status, data: {backups: [...]}}
            data = response.get("data")
            if isinstance(data, dict) and "backups" in data:
                emit(ctx, data["backups"])
            else:
                emit(ctx, response)
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    @app.command("backup-delete")
    def delete_backup(
        ctx: typer.Context,
        backup_id: Annotated[int, typer.Argument(help="Backup ID.")],
        yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    ) -> None:
        """Delete a backup."""
        confirm_or_exit(
            f"Delete backup {backup_id}? The data cannot be recovered after this.",
            yes=yes,
        )
        try:
            emit(ctx, _backup_client(ctx).delete_backup(backup_id))
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    # ---------- restore ----------

    @app.command(
        "restore",
        help=f"Restore a {spec.display} backup into a target cluster.",
    )
    def initiate_restore(
        ctx: typer.Context,
        backup_id: Annotated[int, typer.Option("--backup-id", help="Backup ID to restore from.")],
        target_cluster: Annotated[
            str,
            typer.Option(
                "--target",
                "-t",
                help="Target cluster name (will be created if missing).",
            ),
        ],
        yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    ) -> None:
        confirm_or_exit(
            f"Restore backup {backup_id} into cluster '{target_cluster}'? "
            "Existing data in the target may be overwritten.",
            yes=yes,
        )
        try:
            emit(
                ctx,
                _backup_client(ctx).initiate_restore(
                    backup_id=backup_id,
                    target_cluster_name=target_cluster,
                ),
            )
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    @app.command("restore-status")
    def restore_status(
        ctx: typer.Context,
        backup_id: Annotated[int, typer.Argument(help="Backup ID the restore is for.")],
    ) -> None:
        """Check the status of an in-progress or completed restore."""
        try:
            emit(ctx, _backup_client(ctx).get_restore_status(backup_id))
        except NeviriCLIError as exc:
            handle_cli_error(exc)

    return app
