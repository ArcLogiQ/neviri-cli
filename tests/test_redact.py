"""Tests for the redaction utility.

The redaction layer is part of the platform's privacy posture (Story 12 AC).
These tests pin which keys are sensitive and which display fields stay
visible.
"""

from __future__ import annotations

from neviri_cli.utils.redact import (
    REDACTED_PLACEHOLDER,
    SENSITIVE_KEYS,
    is_sensitive_key,
    redact,
)

# ---------- is_sensitive_key matching ----------


def test_password_is_sensitive() -> None:
    assert is_sensitive_key("password")
    assert is_sensitive_key("Password")
    assert is_sensitive_key("PASSWORD")


def test_razorpay_payment_id_is_sensitive_any_form() -> None:
    assert is_sensitive_key("razorpay_payment_id")
    assert is_sensitive_key("razorpayPaymentId")
    assert is_sensitive_key("razorpay-payment-id")
    assert is_sensitive_key("RazorpayPaymentId")


def test_razorpay_signature_is_sensitive() -> None:
    assert is_sensitive_key("razorpay_signature")
    assert is_sensitive_key("razorpaySignature")


def test_display_fields_not_sensitive() -> None:
    # These are deliberately visible: needed for users to identify their own
    # cards/orders and to complete Razorpay flows.
    assert not is_sensitive_key("razorpay_order_id")
    assert not is_sensitive_key("razorpay_key_id")
    assert not is_sensitive_key("card_brand")
    assert not is_sensitive_key("card_last4")
    assert not is_sensitive_key("card_exp_month")
    assert not is_sensitive_key("card_exp_year")
    assert not is_sensitive_key("email")
    assert not is_sensitive_key("name")
    assert not is_sensitive_key("amount")
    assert not is_sensitive_key("currency")


def test_token_field_not_redacted_by_default() -> None:
    """`neviri auth token` prints the JWT; don't mask all 'token' fields."""
    assert not is_sensitive_key("token")
    assert not is_sensitive_key("refreshToken")


def test_verification_tokens_are_sensitive() -> None:
    assert is_sensitive_key("verification_token")
    assert is_sensitive_key("verificationToken")
    assert is_sensitive_key("reset_password_token")


def test_db_passwords_are_sensitive() -> None:
    assert is_sensitive_key("mysql_pass")
    assert is_sensitive_key("postgres_pass")
    assert is_sensitive_key("mongo_pass")


# ---------- redact() recursion ----------


def test_redact_top_level_dict() -> None:
    out = redact({"password": "secret", "name": "alice"})
    assert out == {"password": REDACTED_PLACEHOLDER, "name": "alice"}


def test_redact_nested_dict() -> None:
    out = redact(
        {
            "user": {"name": "alice", "password": "secret"},
            "razorpay_payment_id": "pay_xyz",
        }
    )
    assert out["user"]["name"] == "alice"
    assert out["user"]["password"] == REDACTED_PLACEHOLDER
    assert out["razorpay_payment_id"] == REDACTED_PLACEHOLDER


def test_redact_list_of_dicts() -> None:
    out = redact(
        [
            {"id": 1, "password": "a"},
            {"id": 2, "razorpay_signature": "sig"},
        ]
    )
    assert out == [
        {"id": 1, "password": REDACTED_PLACEHOLDER},
        {"id": 2, "razorpay_signature": REDACTED_PLACEHOLDER},
    ]


def test_redact_preserves_card_display_fields() -> None:
    out = redact(
        {
            "razorpay_payment_id": "pay_xyz",
            "card_brand": "Visa",
            "card_last4": "1234",
            "card_exp_month": 12,
            "card_exp_year": 2030,
        }
    )
    assert out["razorpay_payment_id"] == REDACTED_PLACEHOLDER
    assert out["card_brand"] == "Visa"
    assert out["card_last4"] == "1234"
    assert out["card_exp_month"] == 12
    assert out["card_exp_year"] == 2030


def test_redact_returns_a_copy_not_a_reference() -> None:
    original = {"password": "secret", "name": "alice"}
    out = redact(original)
    assert original["password"] == "secret"  # original untouched
    assert out["password"] == REDACTED_PLACEHOLDER


def test_redact_handles_scalars() -> None:
    assert redact(42) == 42
    assert redact("hello") == "hello"
    assert redact(None) is None
    assert redact(True) is True


def test_redact_handles_tuples() -> None:
    out = redact(({"password": "a"}, "scalar"))
    assert out == ({"password": REDACTED_PLACEHOLDER}, "scalar")


def test_sensitive_keys_constant_is_frozen() -> None:
    # Tests rely on SENSITIVE_KEYS being immutable so we don't accidentally
    # mutate it from a test.
    assert isinstance(SENSITIVE_KEYS, frozenset)
