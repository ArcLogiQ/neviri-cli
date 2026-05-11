"""Tests for CreditClient, PaymentClient, and PaymentMethodClient."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from neviri_cli.client.base import BaseClient
from neviri_cli.client.credit import CREDITS_PREFIX, RAZORPAY_PREFIX, CreditClient
from neviri_cli.client.payment import (
    PAYMENT_METHOD_PREFIX,
    PAYMENT_PREFIX,
    PaymentClient,
    PaymentMethodClient,
)

BASE = "https://api.example.test"


def _credit() -> CreditClient:
    return CreditClient(BaseClient(BASE, token="t"))


def _payment() -> PaymentClient:
    return PaymentClient(BaseClient(BASE, token="t"))


def _method() -> PaymentMethodClient:
    return PaymentMethodClient(BaseClient(BASE, token="t"))


# ---------- CreditClient ----------


@respx.mock
def test_get_balance() -> None:
    respx.get(f"{BASE}{CREDITS_PREFIX}/balance").mock(
        return_value=httpx.Response(200, json={"balance": 100, "next_expiry": None})
    )
    assert _credit().get_balance()["balance"] == 100


@respx.mock
def test_get_status() -> None:
    respx.get(f"{BASE}{CREDITS_PREFIX}/status").mock(
        return_value=httpx.Response(
            200,
            json={"balance": 100, "credits_exhausted": False, "alert_thresholds": [50, 10]},
        )
    )
    out = _credit().get_status()
    assert out["balance"] == 100
    assert out["credits_exhausted"] is False


@respx.mock
def test_get_transactions_default_pagination() -> None:
    route = respx.get(f"{BASE}{CREDITS_PREFIX}/transactions").mock(
        return_value=httpx.Response(200, json={"transactions": [], "total": 0})
    )
    _credit().get_transactions()
    qs = route.calls.last.request.url.query.decode()
    assert "limit=20" in qs
    assert "offset=0" in qs


@respx.mock
def test_get_transactions_with_type_filter() -> None:
    route = respx.get(f"{BASE}{CREDITS_PREFIX}/transactions").mock(
        return_value=httpx.Response(200, json={"transactions": []})
    )
    _credit().get_transactions(limit=50, offset=10, transaction_type="debit")
    qs = route.calls.last.request.url.query.decode()
    assert "limit=50" in qs
    assert "offset=10" in qs
    assert "type=debit" in qs


@respx.mock
def test_create_razorpay_order() -> None:
    route = respx.post(f"{BASE}{RAZORPAY_PREFIX}/create-order").mock(
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
    out = _credit().create_razorpay_order(100.0)
    assert out["id"] == "ord_xyz"
    body = route.calls.last.request.read().decode()
    assert "100" in body
    assert "credit_topup" in body


# ---------- PaymentClient ----------


@respx.mock
def test_list_payments() -> None:
    respx.get(f"{BASE}{PAYMENT_PREFIX}/history").mock(
        return_value=httpx.Response(
            200, json={"payments": [{"id": 1, "amount": 100, "status": "paid"}]}
        )
    )
    out = _payment().list_payments()
    assert out["payments"][0]["amount"] == 100


@respx.mock
def test_get_summary() -> None:
    respx.get(f"{BASE}{PAYMENT_PREFIX}/summary").mock(
        return_value=httpx.Response(200, json={"total_amount": 500, "total_payments": 5})
    )
    out = _payment().get_summary()
    assert out["total_amount"] == 500


@respx.mock
def test_get_monthly_summary() -> None:
    route = respx.get(f"{BASE}{PAYMENT_PREFIX}/monthly-summary").mock(
        return_value=httpx.Response(200, json={"clusters": []})
    )
    _payment().get_monthly_summary(month="2026-05", cluster="my-cluster")
    qs = route.calls.last.request.url.query.decode()
    assert "month=2026-05" in qs
    assert "cluster=my-cluster" in qs


@respx.mock
def test_get_cluster_paid_total() -> None:
    respx.get(f"{BASE}{PAYMENT_PREFIX}/cluster-paid-total/c1").mock(
        return_value=httpx.Response(200, json={"total": 42.5})
    )
    assert _payment().get_cluster_paid_total("c1")["total"] == 42.5


# ---------- PDF downloads ----------


@respx.mock
def test_download_receipt_writes_pdf(tmp_path: Path) -> None:
    payload = b"%PDF-1.4\n...fake pdf bytes..."
    respx.get(f"{BASE}{PAYMENT_PREFIX}/receipt/42").mock(
        return_value=httpx.Response(
            200, content=payload, headers={"content-type": "application/pdf"}
        )
    )
    dest = tmp_path / "receipt.pdf"
    written = _payment().download_receipt(42, dest)
    assert dest.read_bytes() == payload
    assert written == len(payload)


@respx.mock
def test_download_invoice(tmp_path: Path) -> None:
    payload = b"%PDF-1.4 invoice"
    respx.get(f"{BASE}{PAYMENT_PREFIX}/invoice/42").mock(
        return_value=httpx.Response(200, content=payload)
    )
    dest = tmp_path / "invoice.pdf"
    _payment().download_invoice(42, dest)
    assert dest.read_bytes() == payload


@respx.mock
def test_download_monthly_invoice_with_month(tmp_path: Path) -> None:
    route = respx.get(f"{BASE}{PAYMENT_PREFIX}/monthly-invoice").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.4 monthly")
    )
    dest = tmp_path / "monthly.pdf"
    _payment().download_monthly_invoice(dest, month="2026-04")
    assert b"month=2026-04" in route.calls.last.request.url.query
    assert dest.exists()


# ---------- PaymentMethodClient ----------


@respx.mock
def test_method_status() -> None:
    respx.get(f"{BASE}{PAYMENT_METHOD_PREFIX}/payment-method-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "has_payment_method": True,
                "card_brand": "Visa",
                "card_last4": "1234",
            },
        )
    )
    out = _method().get_status()
    assert out["card_brand"] == "Visa"


@respx.mock
def test_method_remove() -> None:
    respx.delete(f"{BASE}{PAYMENT_METHOD_PREFIX}/remove-payment-method").mock(
        return_value=httpx.Response(200, json={"message": "Payment method removed"})
    )
    assert "removed" in _method().remove()["message"]
