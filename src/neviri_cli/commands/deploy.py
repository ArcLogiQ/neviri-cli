"""`neviri deploy` subcommands. Wraps ``/api/v1/deployments/*``.

A deployment is created by ``neviri app upload`` and then walks 4 stages:

    1. build   -> kpack builds the container image
    2. deploy  -> K8s deployment is rolled out
    3. service -> K8s service is created
    4. ingress -> ingress + TLS cert is provisioned

Each stage is one POST; ``neviri deploy run`` chains all four for the common
case. The backend has no rollback or log-streaming endpoint, so:

- ``neviri deploy rollback`` is intentionally NOT implemented (would need a
  backend endpoint).
- ``neviri deploy logs -f`` polls the deployment status and prints
  ``build_log`` deltas. It is not a true stream.
"""

from __future__ import annotations

import sys
import time
from typing import Annotated, Any

import typer

from neviri_cli.client.deployment import DeploymentClient
from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import emit
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error

deploy_app = typer.Typer(
    name="deploy",
    help="Drive a deployment through its build / deploy / service / ingress stages.",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> DeploymentClient:
    return DeploymentClient(make_client(ctx))


@deploy_app.command("get")
def get_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Show full deployment status (all 4 stages + image_tag + url)."""
    try:
        emit(ctx, _client(ctx).get_deployment(deployment_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@deploy_app.command("manifests")
def get_manifests(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Print the K8s manifests (Deployment / Service / Ingress YAML)."""
    try:
        emit(ctx, _client(ctx).get_manifests(deployment_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- per-stage triggers ----------


@deploy_app.command("build")
def build(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Trigger stage 1 (kpack image build)."""
    try:
        emit(ctx, _client(ctx).trigger_build(deployment_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@deploy_app.command("deploy")
def deploy_stage(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Trigger stage 2 (K8s Deployment rollout)."""
    try:
        emit(ctx, _client(ctx).trigger_deploy(deployment_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@deploy_app.command("service")
def service(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Trigger stage 3 (K8s Service creation)."""
    try:
        emit(ctx, _client(ctx).trigger_service(deployment_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@deploy_app.command("ingress")
def ingress(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Trigger stage 4 (ingress + TLS)."""
    try:
        emit(ctx, _client(ctx).trigger_ingress(deployment_id))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- chained convenience ----------


@deploy_app.command("run")
def run_all_stages(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Trigger all four stages (build -> deploy -> service -> ingress) in order.

    Each stage POST is a 202; this command doesn't wait for completion of one
    stage before triggering the next. Use ``neviri deploy logs -f <id>`` (or
    ``neviri deploy get <id>``) to track progress separately.

    Example:

        neviri deploy run 11
    """
    try:
        client = _client(ctx)
        results = {
            "build": client.trigger_build(deployment_id),
            "deploy": client.trigger_deploy(deployment_id),
            "service": client.trigger_service(deployment_id),
            "ingress": client.trigger_ingress(deployment_id),
        }
        emit(ctx, results)
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- logs (polling-based) ----------


def _extract_log_lines(deployment: dict[str, Any]) -> list[str]:
    log = deployment.get("build_log") or deployment.get("buildLog") or ""
    if not isinstance(log, str):
        return []
    return log.splitlines()


@deploy_app.command("logs")
def logs(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
    follow: Annotated[
        bool,
        typer.Option(
            "--follow",
            "-f",
            help="Poll for new build_log content every --interval seconds.",
        ),
    ] = False,
    tail: Annotated[
        int | None,
        typer.Option(
            "--tail",
            help="Show only the last N lines of the build log.",
            min=1,
        ),
    ] = None,
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            help="Polling interval in seconds when --follow is set.",
            min=0.5,
            max=30.0,
        ),
    ] = 2.0,
) -> None:
    """Print the deployment's build log.

    Phase 2 limitation: the backend exposes ``build_log`` as a single string
    on the deployment record - there's no streaming endpoint. ``--follow``
    polls the deployment every ``--interval`` seconds and prints lines that
    weren't there last time. ``--since`` is not supported because the log
    has no per-line timestamps.
    """
    try:
        client = _client(ctx)

        # One-shot first dump.
        deployment = client.get_deployment(deployment_id)
        lines = _extract_log_lines(deployment)
        if tail is not None:
            lines = lines[-tail:]
        for line in lines:
            typer.echo(line)

        if not follow:
            return

        seen = len(_extract_log_lines(deployment))
        try:
            while True:
                time.sleep(interval)
                deployment = client.get_deployment(deployment_id)
                all_lines = _extract_log_lines(deployment)
                for line in all_lines[seen:]:
                    typer.echo(line)
                    sys.stdout.flush()
                seen = len(all_lines)

                # If all stages are done or errored, stop following.
                statuses = {
                    deployment.get(k)
                    for k in ("build_status", "deploy_status", "service_status", "ingress_status")
                    if deployment.get(k) is not None
                }
                if statuses and statuses.issubset({"succeeded", "failed", "error"}):
                    break
        except KeyboardInterrupt:
            typer.echo("", err=True)  # newline after ^C
            return
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- explicit `rollback` placeholder (NOT implemented) ----------
# The proposal lists `neviri deploy rollback --to <revision>`. The backend
# has no rollback endpoint. To roll back today, find the older deployment ID
# via `neviri app deployments <app-id>` and re-trigger its build/deploy
# stages. Add `rollback` here when the backend ships POST /deployments/{id}/rollback.


@deploy_app.command("rollback", hidden=True)
def rollback_not_implemented(
    ctx: typer.Context,
    deployment_id: Annotated[int, typer.Argument(help="Deployment ID.")],
) -> None:
    """Rollback is not yet supported by the backend."""
    del ctx, deployment_id
    handle_cli_error(
        UserError(
            "rollback is not implemented: the backend has no rollback endpoint. "
            "To roll back, find the previous deployment via "
            "`neviri app deployments <app-id>` and re-trigger its stages with "
            "`neviri deploy deploy <previous-deployment-id>`."
        )
    )
