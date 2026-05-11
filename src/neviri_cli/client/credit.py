"""Typed wrapper for ``/api/v1/credits/*`` (read-only) plus the Razorpay
order-creation endpoint used by ``neviri credit top-up``.

Top-up itself can't complete in a CLI — Razorpay's hosted page handles the
card entry. The CLI creates the order and returns the order_id + key_id so
the user can complete payment in a browser.
"""

from __future__ import annotations

from typing import Any

from neviri_cli.client.base import BaseClient

CREDITS_PREFIX = "/api/v1/credits"
RAZORPAY_PREFIX = "/api/v1/payment/razorpay"


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class CreditClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def get_balance(self) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{CREDITS_PREFIX}/balance"))

    def get_status(self) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{CREDITS_PREFIX}/status"))

    def get_transactions(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        transaction_type: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        if transaction_type:
            params["type"] = transaction_type
        return _as_dict(self._base.get(f"{CREDITS_PREFIX}/transactions", params=params))

    def create_razorpay_order(
        self,
        amount: float,
        *,
        cluster_name: str = "",
        payment_type: str = "credit_topup",
    ) -> dict[str, Any]:
        """Create a Razorpay order for a credit top-up.

        Returns an order envelope from Razorpay (id, amount, currency,
        key_id). The user completes payment via Razorpay's hosted page,
        outside the CLI.
        """
        body = {
            "amount": amount,
            "clusterName": cluster_name,
            "paymentType": payment_type,
        }
        return _as_dict(self._base.post(f"{RAZORPAY_PREFIX}/create-order", json=body))
