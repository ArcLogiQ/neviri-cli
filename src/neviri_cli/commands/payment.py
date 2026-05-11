"""`neviri payment` subcommands.

Wraps ``/api/v1/payment/*`` and ``/api/v1/payment-method/*``.

What the CLI can NOT do (per safety rules + backend design):
- Add a payment method via the CLI. The backend's ``save-payment-method``
  expects a ``razorpay_payment_id`` produced by Razorpay's JS SDK in a
  browser. CLI never collects card data. ``neviri payment method add``
  errors with a pointer to the web UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from neviri_cli.client.factory import make_client
from neviri_cli.client.payment import PaymentClient, PaymentMethodClient
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, UserError, handle_cli_error
from neviri_cli.utils.redact import redact

payment_app = typer.Typer(
    name="payment",
    help="View payment history, download invoices, manage saved payment methods.",
    no_args_is_help=True,
)

method_app = typer.Typer(
    name="method",
    help="Manage your saved payment method.",
    no_args_is_help=True,
)
payment_app.add_typer(method_app, name="method")


def _payment(ctx: typer.Context) -> PaymentClient:
    return PaymentClient(make_client(ctx))


def _method(ctx: typer.Context) -> PaymentMethodClient:
    return PaymentMethodClient(make_client(ctx))


# ---------- payment list / summary ----------


@payment_app.command("list")
def list_payments(ctx: typer.Context) -> None:
    """Show payment history.

    Example:

        neviri payment list
    """
    try:
        response = _payment(ctx).list_payments()
        # Backend returns {"payments": [...]} — pull the inner list when present.
        payments = response.get("payments") if isinstance(response, dict) else None
        emit(ctx, redact(payments if payments is not None else response))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@payment_app.command("summary")
def get_summary(ctx: typer.Context) -> None:
    """Show payment summary statistics."""
    try:
        emit(ctx, redact(_payment(ctx).get_summary()))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@payment_app.command("monthly-summary")
def get_monthly_summary(
    ctx: typer.Context,
    month: Annotated[
        str | None,
        typer.Option("--month", "-m", help="Billing month in YYYY-MM format."),
    ] = None,
    cluster: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Cluster name or 'all'."),
    ] = "all",
) -> None:
    """Show per-cluster cost breakdown for a billing month.

    Example:

        neviri payment monthly-summary --month 2026-05
    """
    try:
        emit(ctx, redact(_payment(ctx).get_monthly_summary(month=month, cluster=cluster)))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@payment_app.command("cluster-total")
def get_cluster_total(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Argument(help="Cluster name.")],
) -> None:
    """Show total amount paid for a cluster."""
    try:
        emit(ctx, redact(_payment(ctx).get_cluster_paid_total(cluster_name)))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- PDF downloads ----------


@payment_app.command("receipt")
def download_receipt(
    ctx: typer.Context,
    payment_id: Annotated[int, typer.Argument(help="Payment ID.")],
    output_file: Annotated[
        Path,
        typer.Option(
            "--output-file",
            "-o",
            help="Local PDF path to write to.",
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ],
) -> None:
    """Download a payment receipt PDF.

    Example:

        neviri payment receipt 42 -o receipt-42.pdf
    """
    try:
        n = _payment(ctx).download_receipt(payment_id, output_file)
        emit(ctx, {"payment_id": payment_id, "wrote": str(output_file), "bytes": n})
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@payment_app.command("invoice")
def download_invoice(
    ctx: typer.Context,
    payment_id: Annotated[int, typer.Argument(help="Payment ID.")],
    output_file: Annotated[
        Path,
        typer.Option(
            "--output-file",
            "-o",
            help="Local PDF path to write to.",
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ],
) -> None:
    """Download a single-payment invoice PDF."""
    try:
        n = _payment(ctx).download_invoice(payment_id, output_file)
        emit(ctx, {"payment_id": payment_id, "wrote": str(output_file), "bytes": n})
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@payment_app.command("monthly-invoice")
def download_monthly_invoice(
    ctx: typer.Context,
    output_file: Annotated[
        Path,
        typer.Option(
            "--output-file",
            "-o",
            help="Local PDF path to write to.",
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ],
    month: Annotated[
        str | None,
        typer.Option("--month", "-m", help="Billing month YYYY-MM (defaults to current)."),
    ] = None,
) -> None:
    """Download the monthly invoice PDF.

    Example:

        neviri payment monthly-invoice --month 2026-04 -o invoice-2026-04.pdf
    """
    try:
        n = _payment(ctx).download_monthly_invoice(output_file, month=month)
        emit(ctx, {"month": month or "current", "wrote": str(output_file), "bytes": n})
    except NeviriCLIError as exc:
        handle_cli_error(exc)


# ---------- payment method ----------


@method_app.command("status")
def method_status(ctx: typer.Context) -> None:
    """Show the saved payment method status (brand / last4 / setup state).

    Example:

        neviri payment method status
    """
    try:
        emit(ctx, redact(_method(ctx).get_status()))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@method_app.command("list")
def method_list(ctx: typer.Context) -> None:
    """Alias for ``payment method status`` (one method per account today)."""
    try:
        emit(ctx, redact(_method(ctx).get_status()))
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@method_app.command("add")
def method_add(ctx: typer.Context) -> None:
    """Adding a payment method is not supported from the CLI.

    Reason: Razorpay's hosted JS SDK collects card data in a browser, and the
    CLI cannot (and per safety rules MUST not) accept card details. Use the
    Neviri dashboard instead.
    """
    del ctx
    handle_cli_error(
        UserError(
            "adding a payment method requires a browser (Razorpay JS SDK). "
            "Open https://console.neviri.com/billing/payment-method to add one."
        )
    )


@method_app.command("delete")
def method_delete(
    ctx: typer.Context,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Remove the saved payment method.

    Example:

        neviri payment method delete --yes
    """
    confirm_or_exit(
        "Remove the saved payment method? "
        "You will need to add one again before scheduling new charges.",
        yes=yes,
    )
    try:
        emit(ctx, redact(_method(ctx).remove()))
    except NeviriCLIError as exc:
        handle_cli_error(exc)
