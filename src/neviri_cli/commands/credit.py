"""`neviri credit` subcommands. Wraps ``/api/v1/credits/*``.

Top-up is partial — Razorpay's hosted page handles the actual card entry
and capture, so the CLI creates the order and prints the order details for
the user to complete in a browser. Per safety rules, this requires explicit
confirmation (``--yes`` or interactive).
"""

from __future__ import annotations

from typing import Annotated

import typer

from neviri_cli.client.credit import CreditClient
from neviri_cli.client.factory import make_client
from neviri_cli.commands._common import confirm_or_exit, emit
from neviri_cli.exceptions import NeviriCLIError, handle_cli_error
from neviri_cli.utils.redact import redact

credit_app = typer.Typer(
    name="credit",
    help="View your credit balance and transaction history; initiate top-ups.",
    no_args_is_help=True,
)


def _client(ctx: typer.Context) -> CreditClient:
    return CreditClient(make_client(ctx))


@credit_app.command("balance")
def get_balance(ctx: typer.Context) -> None:
    """Show the current credit balance and next expiry.

    Example:

        neviri credit balance
    """
    try:
        emit(ctx, _client(ctx).get_balance())
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@credit_app.command("status")
def get_status(ctx: typer.Context) -> None:
    """Show full credit status (balance + alert thresholds + exhaustion flag)."""
    try:
        emit(ctx, _client(ctx).get_status())
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@credit_app.command("history")
def get_history(
    ctx: typer.Context,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Number of records to fetch.", min=1, max=100),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Skip the first N records.", min=0),
    ] = 0,
    txn_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by transaction type."),
    ] = None,
) -> None:
    """Show paginated credit transaction history.

    Example:

        neviri credit history --limit 50
        neviri credit history --type debit
    """
    try:
        response = _client(ctx).get_transactions(
            limit=limit, offset=offset, transaction_type=txn_type
        )
        # Backend returns {transactions: [...], total: N, ...} — emit the envelope.
        emit(ctx, response)
    except NeviriCLIError as exc:
        handle_cli_error(exc)


@credit_app.command("top-up")
def top_up(
    ctx: typer.Context,
    amount: Annotated[
        float,
        typer.Option(
            "--amount",
            "-a",
            help="Amount to charge in your account's currency.",
            min=1,
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Confirm initiating the Razorpay order without prompting.",
        ),
    ] = False,
) -> None:
    """Initiate a Razorpay top-up order.

    The CLI cannot actually charge a card — Razorpay's hosted payment page
    does that. This command creates the order and prints the order_id +
    key_id so you can complete payment in a browser.

    Example:

        neviri credit top-up --amount 100 --yes
    """
    confirm_or_exit(
        f"Initiate a Razorpay top-up order for {amount}? "
        "You'll need to complete the payment in a browser.",
        yes=yes,
    )
    try:
        order = _client(ctx).create_razorpay_order(amount)
        # Redact any returned credential fields defensively (the order
        # response should only have public identifiers, but the backend's
        # schema is loose).
        emit(ctx, redact(order))
        typer.echo(
            "\nNext step: open the Neviri dashboard at "
            "https://console.neviri.com/billing/topup to complete this order.",
            err=True,
        )
    except NeviriCLIError as exc:
        handle_cli_error(exc)
