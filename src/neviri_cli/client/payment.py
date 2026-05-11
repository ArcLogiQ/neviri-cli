"""Typed wrappers for ``/api/v1/payment/*`` and ``/api/v1/payment-method/*``.

PDF download endpoints (receipt, invoice, monthly-invoice) stream the body to
a local file so the full PDF never sits in CLI memory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neviri_cli.client.base import BaseClient

PAYMENT_PREFIX = "/api/v1/payment"
PAYMENT_METHOD_PREFIX = "/api/v1/payment-method"


def _as_dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


class PaymentClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def list_payments(self) -> dict[str, Any]:
        """Returns ``{payments: [...]}`` on the wire (backend's chosen shape)."""
        return _as_dict(self._base.get(f"{PAYMENT_PREFIX}/history"))

    def get_summary(self) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PAYMENT_PREFIX}/summary"))

    def get_monthly_summary(
        self, *, month: str | None = None, cluster: str = "all"
    ) -> dict[str, Any]:
        params: dict[str, str] = {"cluster": cluster}
        if month:
            params["month"] = month
        return _as_dict(self._base.get(f"{PAYMENT_PREFIX}/monthly-summary", params=params))

    def get_cluster_paid_total(self, cluster_name: str) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PAYMENT_PREFIX}/cluster-paid-total/{cluster_name}"))

    # --- PDF downloads (binary, streamed to file) -------------------

    def download_receipt(self, payment_id: int, dest: Path) -> int:
        return self._download_pdf(f"{PAYMENT_PREFIX}/receipt/{payment_id}", dest)

    def download_invoice(self, payment_id: int, dest: Path) -> int:
        return self._download_pdf(f"{PAYMENT_PREFIX}/invoice/{payment_id}", dest)

    def download_monthly_invoice(self, dest: Path, *, month: str | None = None) -> int:
        params = {"month": month} if month else None
        # The httpx streaming API takes params; build the URL manually so the
        # request still appears at the canonical path in our test mocks.
        url = f"{PAYMENT_PREFIX}/monthly-invoice"
        return self._download_pdf(url, dest, params=params)

    def _download_pdf(
        self,
        url: str,
        dest: Path,
        *,
        params: dict[str, str] | None = None,
        chunk_size: int = 64 * 1024,
    ) -> int:
        total = 0
        with self._base._client.stream("GET", url, params=params) as response:
            if response.status_code >= 400:
                response.read()
                self._base._raise_for_response(response)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as out:
                for chunk in response.iter_bytes(chunk_size):
                    if not chunk:
                        continue
                    out.write(chunk)
                    total += len(chunk)
        return total


class PaymentMethodClient:
    """Wraps ``/api/v1/payment-method/*``.

    Note: ``save-payment-method`` is intentionally not exposed - it requires a
    ``razorpay_payment_id`` that can only be produced by Razorpay's JS SDK in
    a browser. CLI cannot collect card data per safety rules.
    """

    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def get_status(self) -> dict[str, Any]:
        return _as_dict(self._base.get(f"{PAYMENT_METHOD_PREFIX}/payment-method-status"))

    def remove(self) -> dict[str, Any]:
        return _as_dict(self._base.delete(f"{PAYMENT_METHOD_PREFIX}/remove-payment-method"))
