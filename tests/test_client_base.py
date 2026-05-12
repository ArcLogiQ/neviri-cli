"""Tests for the httpx wrapper at neviri_cli.client.base.

Uses respx to mock httpx transport without hitting the network.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from neviri_cli.client.base import BaseClient, unwrap_response
from neviri_cli.exceptions import (
    AuthError,
    NetworkError,
    NeviriCLIError,
    ServerError,
    UserError,
)

BASE = "https://api.example.test"


# ---------- unwrap_response (the response-wrapper workaround) ----------


def test_unwrap_response_strips_envelope_for_array_payloads() -> None:
    raw = {"status": True, "data": [{"id": 1}, {"id": 2}], "message": "Success"}
    assert unwrap_response(raw) == [{"id": 1}, {"id": 2}]


def test_unwrap_response_passes_through_dict_payloads() -> None:
    raw = {"id": 5, "name": "alice"}
    assert unwrap_response(raw) == raw


def test_unwrap_response_passes_through_dict_with_data_string() -> None:
    # If `data` is not a list, the wrapper middleware never wraps it -
    # this dict is the response itself, leave it alone.
    raw = {"status": "ok", "data": "not-a-list"}
    assert unwrap_response(raw) == raw


def test_unwrap_response_passes_through_lists() -> None:
    raw = [1, 2, 3]
    assert unwrap_response(raw) == raw


# ---------- BaseClient happy paths ----------


@respx.mock
def test_get_returns_unwrapped_list() -> None:
    respx.get(f"{BASE}/api/v1/vm/all").mock(
        return_value=httpx.Response(
            200,
            json={"status": True, "data": [{"id": 1}], "message": "Success"},
        )
    )
    with BaseClient(BASE, token="t") as c:
        result = c.get("/api/v1/vm/all")
    assert result == [{"id": 1}]


@respx.mock
def test_get_returns_dict_unmodified() -> None:
    respx.get(f"{BASE}/api/v1/credit/balance").mock(
        return_value=httpx.Response(200, json={"balance": 100, "currency": "USD"})
    )
    with BaseClient(BASE, token="t") as c:
        result = c.get("/api/v1/credit/balance")
    assert result == {"balance": 100, "currency": "USD"}


@respx.mock
def test_authorization_header_uses_bearer_token() -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, json={"ok": True}))
    with BaseClient(BASE, token="my-token") as c:
        c.get("/x")
    assert route.calls.last.request.headers["authorization"] == "Bearer my-token"


@respx.mock
def test_no_authorization_header_when_no_token() -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, json={"ok": True}))
    with BaseClient(BASE) as c:
        c.get("/x")
    assert "authorization" not in route.calls.last.request.headers


@respx.mock
def test_request_id_captured_from_response_header() -> None:
    respx.get(f"{BASE}/x").mock(
        return_value=httpx.Response(200, json={"ok": True}, headers={"X-Request-ID": "req-42"})
    )
    with BaseClient(BASE) as c:
        c.get("/x")
        assert c.last_request_id == "req-42"


@respx.mock
def test_post_put_patch_delete_route_through_request() -> None:
    respx.post(f"{BASE}/x").mock(return_value=httpx.Response(201, json={"ok": True}))
    respx.put(f"{BASE}/x").mock(return_value=httpx.Response(200, json={"ok": True}))
    respx.patch(f"{BASE}/x").mock(return_value=httpx.Response(200, json={"ok": True}))
    respx.delete(f"{BASE}/x").mock(return_value=httpx.Response(204))
    with BaseClient(BASE) as c:
        assert c.post("/x", json={"a": 1}) == {"ok": True}
        assert c.put("/x", json={"a": 1}) == {"ok": True}
        assert c.patch("/x", json={"a": 1}) == {"ok": True}
        assert c.delete("/x") is None


@respx.mock
def test_non_json_response_returned_as_text() -> None:
    respx.get(f"{BASE}/raw").mock(
        return_value=httpx.Response(200, text="hello", headers={"content-type": "text/plain"})
    )
    with BaseClient(BASE) as c:
        assert c.get("/raw") == "hello"


# ---------- error mapping ----------


@respx.mock
def test_401_raises_auth_error_with_message_and_request_id() -> None:
    respx.get(f"{BASE}/x").mock(
        return_value=httpx.Response(
            401,
            json={"message": "token expired"},
            headers={"X-Request-ID": "r-1"},
        )
    )
    with BaseClient(BASE) as c, pytest.raises(AuthError) as info:
        c.get("/x")
    assert info.value.message == "token expired"
    assert info.value.request_id == "r-1"
    assert info.value.exit_code == 3


@respx.mock
def test_403_raises_auth_error() -> None:
    respx.get(f"{BASE}/x").mock(return_value=httpx.Response(403, json={"detail": "forbidden"}))
    with BaseClient(BASE) as c, pytest.raises(AuthError) as info:
        c.get("/x")
    assert info.value.message == "forbidden"


@respx.mock
def test_400_raises_user_error() -> None:
    respx.post(f"{BASE}/x").mock(return_value=httpx.Response(400, json={"message": "bad name"}))
    with BaseClient(BASE) as c, pytest.raises(UserError) as info:
        c.post("/x", json={})
    assert info.value.message == "bad name"
    assert info.value.exit_code == 2


@respx.mock
def test_500_raises_server_error() -> None:
    respx.get(f"{BASE}/x").mock(return_value=httpx.Response(500, json={"error": "boom"}))
    with BaseClient(BASE, max_retries=0) as c, pytest.raises(ServerError) as info:
        c.get("/x")
    assert info.value.message == "boom"
    assert info.value.exit_code == 5


@respx.mock
def test_invalid_json_raises_generic() -> None:
    respx.get(f"{BASE}/x").mock(
        return_value=httpx.Response(
            200,
            content=b"not json",
            headers={"content-type": "application/json"},
        )
    )
    with BaseClient(BASE) as c, pytest.raises(NeviriCLIError):
        c.get("/x")


# ---------- retry behaviour ----------


@respx.mock
def test_retries_503_then_succeeds() -> None:
    route = respx.get(f"{BASE}/x").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    with BaseClient(BASE, max_retries=3, retry_backoff=0.0) as c:
        result = c.get("/x")
    assert result == {"ok": True}
    assert route.call_count == 3


@respx.mock
def test_retries_exhausted_raises_server_error() -> None:
    respx.get(f"{BASE}/x").mock(return_value=httpx.Response(503))
    with BaseClient(BASE, max_retries=2, retry_backoff=0.0) as c, pytest.raises(ServerError):
        c.get("/x")


@respx.mock
def test_429_is_retried() -> None:
    route = respx.get(f"{BASE}/x").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"ok": True})]
    )
    with BaseClient(BASE, max_retries=2, retry_backoff=0.0) as c:
        c.get("/x")
    assert route.call_count == 2


@respx.mock
def test_400_is_not_retried() -> None:
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(400, json={"message": "no"}))
    with BaseClient(BASE, max_retries=3, retry_backoff=0.0) as c, pytest.raises(UserError):
        c.get("/x")
    assert route.call_count == 1


@respx.mock
def test_timeout_is_retried_then_raises_network_error() -> None:
    respx.get(f"{BASE}/x").mock(side_effect=httpx.TimeoutException("slow"))
    with BaseClient(BASE, max_retries=1, retry_backoff=0.0) as c, pytest.raises(NetworkError):
        c.get("/x")


@respx.mock
def test_transport_error_is_retried_then_raises_network_error() -> None:
    respx.get(f"{BASE}/x").mock(side_effect=httpx.ConnectError("refused"))
    with BaseClient(BASE, max_retries=1, retry_backoff=0.0) as c, pytest.raises(NetworkError):
        c.get("/x")


# ---------- url joining / construction ----------


def test_base_url_trailing_slash_stripped() -> None:
    c = BaseClient(BASE + "/", token="t")
    assert c._base_url == BASE  # type: ignore[reportPrivateUsage]
    c.close()


def test_max_retries_clamped_to_zero() -> None:
    c = BaseClient(BASE, max_retries=-5)
    assert c._max_retries == 0  # type: ignore[reportPrivateUsage]
    c.close()


# ---------- --debug request/response logging ----------


@respx.mock
def test_debug_logs_request_and_response_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(f"{BASE}/v1/hello").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True},
            headers={"X-Request-ID": "req-1"},
        )
    )
    client = BaseClient(BASE, token="secret-bearer", debug=True)
    try:
        out = client.get("/v1/hello")
    finally:
        client.close()
    assert out == {"ok": True}
    captured = capsys.readouterr()
    # No debug output should ever land on stdout (so JSON pipelines stay clean)
    assert captured.out == ""
    # Both request and response lines on stderr
    assert "--> GET https://api.example.test/v1/hello" in captured.err
    assert "<-- 200" in captured.err
    # Body of the response shows up
    assert '"ok": true' in captured.err


@respx.mock
def test_debug_redacts_authorization_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(f"{BASE}/v1/me").mock(return_value=httpx.Response(200, json={"id": 1}))
    client = BaseClient(BASE, token="super-secret-token", debug=True)
    try:
        client.get("/v1/me")
    finally:
        client.close()
    captured = capsys.readouterr()
    assert "super-secret-token" not in captured.err
    assert "Bearer" not in captured.err  # whole value gets replaced
    assert "***" in captured.err


@respx.mock
def test_debug_redacts_password_in_request_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.post(f"{BASE}/v1/login").mock(return_value=httpx.Response(200, json={"token": "abc"}))
    client = BaseClient(BASE, debug=True)
    try:
        client.post("/v1/login", json={"email": "alice@example.com", "password": "hunter2"})
    finally:
        client.close()
    captured = capsys.readouterr()
    assert "hunter2" not in captured.err
    assert "alice@example.com" in captured.err  # email NOT sensitive
    assert "***" in captured.err


@respx.mock
def test_debug_redacts_tokens_in_response_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.post(f"{BASE}/v1/login").mock(
        return_value=httpx.Response(
            200,
            json={
                "user": {"email": "alice@example.com", "name": "Alice"},
                "access_token": "AT-leaky",
                "refresh_token": "RT-leaky",
                "token": "scoped",
            },
        )
    )
    client = BaseClient(BASE, debug=True)
    try:
        client.post("/v1/login", json={"email": "alice@example.com"})
    finally:
        client.close()
    captured = capsys.readouterr()
    assert "AT-leaky" not in captured.err
    assert "RT-leaky" not in captured.err
    # bare `token` is still shown (used by `neviri auth token`)
    assert "scoped" in captured.err
    assert "Alice" in captured.err
    assert "alice@example.com" in captured.err


@respx.mock
def test_debug_redacts_set_cookie_in_response_headers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(f"{BASE}/v1/x").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True},
            headers={"Set-Cookie": "session=secret-cookie-value; HttpOnly"},
        )
    )
    client = BaseClient(BASE, debug=True)
    try:
        client.get("/v1/x")
    finally:
        client.close()
    captured = capsys.readouterr()
    assert "secret-cookie-value" not in captured.err
    assert "***" in captured.err


@respx.mock
def test_debug_off_by_default_emits_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(f"{BASE}/v1/q").mock(return_value=httpx.Response(200, json={"ok": True}))
    client = BaseClient(BASE, token="t")
    try:
        client.get("/v1/q")
    finally:
        client.close()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


@respx.mock
def test_debug_truncates_long_non_json_response_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    big = "A" * 2000
    respx.get(f"{BASE}/v1/blob").mock(
        return_value=httpx.Response(200, text=big, headers={"Content-Type": "text/plain"})
    )
    client = BaseClient(BASE, debug=True)
    try:
        client.get("/v1/blob")
    finally:
        client.close()
    captured = capsys.readouterr()
    assert "[truncated]" in captured.err
    # Should NOT contain the full 2000-A blob
    assert "A" * 1500 not in captured.err
