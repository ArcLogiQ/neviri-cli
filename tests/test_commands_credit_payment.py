"""End-to-end tests for `neviri credit` and `neviri payment`.

Also pins redaction behavior at the command output layer: razorpay_payment_id
and razorpay_signature in returned payloads must be masked; card_last4 must
remain visible (Story 12 AC).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token
from neviri_cli.utils.redact import REDACTED_PLACEHOLDER

BACKEND = "http://localhost:8000"
CREDITS = "/api/v1/credits"
RAZORPAY = "/api/v1/payment/razorpay"
PAYMENT = "/api/v1/payment"
METHOD = "/api/v1/payment-method"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


# ============================================================
# neviri credit
# ============================================================


@respx.mock
def test_credit_balance(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{CREDITS}/balance").mock(
        return_value=httpx.Response(200, json={"balance": 100, "next_expiry": None})
    )
    result = runner.invoke(app, ["--output", "json", "credit", "balance"])
    assert result.exit_code == 0
    assert "100" in result.stdout


@respx.mock
def test_credit_status(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{CREDITS}/status").mock(
        return_value=httpx.Response(
            200, json={"balance": 100, "credits_exhausted": False, "alert_thresholds": [50, 10]}
        )
    )
    result = runner.invoke(app, ["--output", "json", "credit", "status"])
    assert result.exit_code == 0


@respx.mock
def test_credit_history_with_filters(logged_in: None, runner: CliRunner) -> None:
    route = respx.get(f"{BACKEND}{CREDITS}/transactions").mock(
        return_value=httpx.Response(
            200, json={"transactions": [{"id": 1, "type": "debit", "amount": 5}], "total": 1}
        )
    )
    result = runner.invoke(
        app,
        ["--output", "json", "credit", "history", "--limit", "50", "--type", "debit"],
    )
    assert result.exit_code == 0
    qs = route.calls.last.request.url.query.decode()
    assert "limit=50" in qs
    assert "type=debit" in qs


@respx.mock
def test_credit_top_up_with_yes_creates_order(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{RAZORPAY}/create-order").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "ord_xyz",
                "amount": 10000,
                "currency": "INR",
                "key_id": "rzp_test_key",
            },
        )
    )
    result = runner.invoke(
        app,
        ["--output", "json", "credit", "top-up", "--amount", "100", "--yes"],
    )
    assert result.exit_code == 0, result.stdout
    assert "ord_xyz" in result.stdout
    # The dashboard URL hint is printed to stderr.
    assert "console.neviri.com" in result.stderr
    body = route.calls.last.request.read().decode()
    assert "100" in body


@respx.mock
def test_credit_top_up_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.post(f"{BACKEND}{RAZORPAY}/create-order").mock(
        return_value=httpx.Response(201, json={"id": "ord_xyz"})
    )
    result = runner.invoke(
        app,
        ["credit", "top-up", "--amount", "100"],
        input="n\n",
    )
    assert result.exit_code == 0
    assert route.call_count == 0  # confirmation rejected; no order created


# ============================================================
# neviri payment
# ============================================================


@respx.mock
def test_payment_list_emits_inner_list(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/history").mock(
        return_value=httpx.Response(
            200, json={"payments": [{"id": 1, "amount": 100, "status": "paid"}]}
        )
    )
    result = runner.invoke(app, ["--output", "json", "payment", "list"])
    assert result.exit_code == 0
    # We unwrap to the inner list so users see [{...}] not {"payments":[{...}]}
    assert result.stdout.strip().startswith("[")


@respx.mock
def test_payment_summary(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/summary").mock(
        return_value=httpx.Response(200, json={"total_amount": 500})
    )
    result = runner.invoke(app, ["--output", "json", "payment", "summary"])
    assert result.exit_code == 0


@respx.mock
def test_payment_monthly_summary(logged_in: None, runner: CliRunner) -> None:
    route = respx.get(f"{BACKEND}{PAYMENT}/monthly-summary").mock(
        return_value=httpx.Response(200, json={"clusters": []})
    )
    result = runner.invoke(
        app, ["payment", "monthly-summary", "--month", "2026-04", "--cluster", "c1"]
    )
    assert result.exit_code == 0
    qs = route.calls.last.request.url.query.decode()
    assert "month=2026-04" in qs
    assert "cluster=c1" in qs


@respx.mock
def test_payment_cluster_total(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/cluster-paid-total/c1").mock(
        return_value=httpx.Response(200, json={"total": 42.5})
    )
    result = runner.invoke(app, ["--output", "json", "payment", "cluster-total", "c1"])
    assert result.exit_code == 0


# ---------- PDF downloads ----------


@respx.mock
def test_payment_receipt_download(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    payload = b"%PDF-1.4\nreceipt-content"
    respx.get(f"{BACKEND}{PAYMENT}/receipt/42").mock(
        return_value=httpx.Response(200, content=payload)
    )
    dest = tmp_path / "r.pdf"
    result = runner.invoke(app, ["payment", "receipt", "42", "-o", str(dest)])
    assert result.exit_code == 0
    assert dest.read_bytes() == payload


@respx.mock
def test_payment_invoice_download(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/invoice/42").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.4 invoice")
    )
    dest = tmp_path / "inv.pdf"
    result = runner.invoke(app, ["payment", "invoice", "42", "-o", str(dest)])
    assert result.exit_code == 0


@respx.mock
def test_payment_monthly_invoice_download(
    logged_in: None, runner: CliRunner, tmp_path: Path
) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/monthly-invoice").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.4 monthly")
    )
    dest = tmp_path / "monthly.pdf"
    result = runner.invoke(
        app, ["payment", "monthly-invoice", "--month", "2026-04", "-o", str(dest)]
    )
    assert result.exit_code == 0
    assert dest.exists()


# ---------- payment method ----------


@respx.mock
def test_method_status(logged_in: None, runner: CliRunner) -> None:
    respx.get(f"{BACKEND}{METHOD}/payment-method-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "has_payment_method": True,
                "card_brand": "Visa",
                "card_last4": "1234",
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "payment", "method", "status"])
    assert result.exit_code == 0
    assert "1234" in result.stdout
    assert "Visa" in result.stdout


@respx.mock
def test_method_list(logged_in: None, runner: CliRunner) -> None:
    """Alias for status — one method per account today."""
    respx.get(f"{BACKEND}{METHOD}/payment-method-status").mock(
        return_value=httpx.Response(200, json={"card_brand": "Visa"})
    )
    result = runner.invoke(app, ["payment", "method", "list"])
    assert result.exit_code == 0


def test_method_add_errors_with_pointer_to_web_ui(isolated_home: Path, runner: CliRunner) -> None:
    store_token("default", "test-token")
    result = runner.invoke(app, ["payment", "method", "add"])
    assert result.exit_code == 2
    assert "browser" in result.stderr
    assert "console.neviri.com" in result.stderr


@respx.mock
def test_method_delete_with_yes(logged_in: None, runner: CliRunner) -> None:
    respx.delete(f"{BACKEND}{METHOD}/remove-payment-method").mock(
        return_value=httpx.Response(200, json={"message": "removed"})
    )
    result = runner.invoke(app, ["payment", "method", "delete", "--yes"])
    assert result.exit_code == 0


@respx.mock
def test_method_delete_aborted(logged_in: None, runner: CliRunner) -> None:
    route = respx.delete(f"{BACKEND}{METHOD}/remove-payment-method").mock(
        return_value=httpx.Response(200, json={"message": "removed"})
    )
    result = runner.invoke(app, ["payment", "method", "delete"], input="n\n")
    assert result.exit_code == 0
    assert route.call_count == 0


# ============================================================
# Redaction in command output (Story 12 AC)
# ============================================================


@respx.mock
def test_payment_list_redacts_razorpay_payment_id(logged_in: None, runner: CliRunner) -> None:
    """Even if the backend returns a razorpay_payment_id in payment history,
    the CLI must mask it before printing."""
    respx.get(f"{BACKEND}{PAYMENT}/history").mock(
        return_value=httpx.Response(
            200,
            json={
                "payments": [
                    {
                        "id": 1,
                        "amount": 100,
                        "razorpay_payment_id": "pay_LIVE_SECRET_xyz",
                        "razorpay_order_id": "ord_xyz",
                    }
                ]
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "payment", "list"])
    assert result.exit_code == 0
    assert "pay_LIVE_SECRET_xyz" not in result.stdout
    assert REDACTED_PLACEHOLDER in result.stdout
    # Order ID is a public identifier; users need it to look up the order.
    assert "ord_xyz" in result.stdout


@respx.mock
def test_method_status_preserves_card_display_fields(logged_in: None, runner: CliRunner) -> None:
    """card_brand / card_last4 are by-design visible — never redacted."""
    respx.get(f"{BACKEND}{METHOD}/payment-method-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "card_brand": "Visa",
                "card_last4": "1234",
                "card_exp_month": 12,
                "card_exp_year": 2030,
            },
        )
    )
    result = runner.invoke(app, ["--output", "json", "payment", "method", "status"])
    assert result.exit_code == 0
    assert "Visa" in result.stdout
    assert "1234" in result.stdout
    assert REDACTED_PLACEHOLDER not in result.stdout


# ============================================================
# Error mapping
# ============================================================


_CP_ERROR_PATHS: list[tuple[str, str, list[str]]] = [
    ("GET", f"{BACKEND}{CREDITS}/balance", ["credit", "balance"]),
    ("GET", f"{BACKEND}{CREDITS}/status", ["credit", "status"]),
    ("GET", f"{BACKEND}{CREDITS}/transactions", ["credit", "history"]),
    (
        "POST",
        f"{BACKEND}{RAZORPAY}/create-order",
        ["credit", "top-up", "--amount", "100", "--yes"],
    ),
    ("GET", f"{BACKEND}{PAYMENT}/history", ["payment", "list"]),
    ("GET", f"{BACKEND}{PAYMENT}/summary", ["payment", "summary"]),
    (
        "GET",
        f"{BACKEND}{PAYMENT}/monthly-summary",
        ["payment", "monthly-summary"],
    ),
    (
        "GET",
        f"{BACKEND}{PAYMENT}/cluster-paid-total/c1",
        ["payment", "cluster-total", "c1"],
    ),
    ("GET", f"{BACKEND}{METHOD}/payment-method-status", ["payment", "method", "status"]),
    (
        "DELETE",
        f"{BACKEND}{METHOD}/remove-payment-method",
        ["payment", "method", "delete", "--yes"],
    ),
]


# PDF downloads need an `-o <tmp_path>` arg so they can't go in the simple
# parametrize - separate tests so the dest path is per-test.


@respx.mock
def test_payment_receipt_500_returns_5(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/receipt/42").mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, ["payment", "receipt", "42", "-o", str(tmp_path / "r.pdf")])
    assert result.exit_code == 5


@respx.mock
def test_payment_invoice_500_returns_5(logged_in: None, runner: CliRunner, tmp_path: Path) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/invoice/42").mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, ["payment", "invoice", "42", "-o", str(tmp_path / "i.pdf")])
    assert result.exit_code == 5


@respx.mock
def test_payment_monthly_invoice_500_returns_5(
    logged_in: None, runner: CliRunner, tmp_path: Path
) -> None:
    respx.get(f"{BACKEND}{PAYMENT}/monthly-invoice").mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, ["payment", "monthly-invoice", "-o", str(tmp_path / "m.pdf")])
    assert result.exit_code == 5


@pytest.mark.parametrize(("method", "url", "argv"), _CP_ERROR_PATHS)
@respx.mock
def test_credit_payment_command_500_returns_5(
    method: str,
    url: str,
    argv: list[str],
    logged_in: None,
    runner: CliRunner,
) -> None:
    getattr(respx, method.lower())(url).mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    result = runner.invoke(app, argv)
    assert result.exit_code == 5, (argv, result.stdout, result.stderr)
