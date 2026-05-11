"""Recursive redaction of sensitive fields in CLI output.

Used by:
- ``commands/payment.py`` for Razorpay credential triples on order/verify responses
- ``commands/_common.py`` (future) when ``--debug`` dumps full request/response
  payloads (Phase 3 security hardening per Story 19)

Design choices documented in CHANGELOG / ADR:
- **Credentials are redacted** (passwords, Razorpay payment_id, Razorpay
  signature, JWT-equivalent secrets).
- **Display fields are preserved** (card_last4, card_brand, card_exp_*,
  razorpay_order_id, razorpay_key_id, email, name). Users need these to
  identify their own cards/orders and to complete Razorpay flows.
- Key matching is case-insensitive and underscore-insensitive
  (``razorpayPaymentId`` and ``razorpay_payment_id`` both hit).
"""

from __future__ import annotations

from typing import Any

# Canonical form: lowercase, no underscores. Add carefully — over-redaction
# breaks UX (e.g. redacting "token" would break `neviri auth token`).
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # User secrets
        "password",
        "currentpassword",
        "newpassword",
        "oldpassword",
        # Razorpay credentials (the triple that proves a charge)
        "razorpaypaymentid",
        "razorpaysignature",
        # DB user passwords (write-only fields; backend doesn't return them
        # but defense in depth)
        "mongopass",
        "mysqlpass",
        "postgrespass",
        # Card number (backend never returns this; defensive)
        "cardnumber",
        "fullcardnumber",
        # Verification tokens (one-time-use but still sensitive)
        "verificationtoken",
        "resetpasswordtoken",
    }
)

REDACTED_PLACEHOLDER = "***"


def _normalize(key: str) -> str:
    return key.replace("_", "").replace("-", "").lower()


def is_sensitive_key(key: str) -> bool:
    """True if ``key`` (in any case/underscore form) matches a sensitive field."""
    return _normalize(key) in SENSITIVE_KEYS


def redact(data: Any) -> Any:
    """Return a deep copy of ``data`` with sensitive field values masked.

    - ``dict`` -> new dict with the same keys, sensitive values replaced
    - ``list`` / ``tuple`` -> new list with each element redacted
    - scalars -> returned unchanged
    """
    if isinstance(data, dict):
        return {
            k: REDACTED_PLACEHOLDER if is_sensitive_key(k) else redact(v) for k, v in data.items()
        }
    if isinstance(data, list):
        return [redact(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact(item) for item in data)
    return data


__all__ = [
    "REDACTED_PLACEHOLDER",
    "SENSITIVE_KEYS",
    "is_sensitive_key",
    "redact",
]
