"""Exit-code contract tests for neviri_cli.exceptions."""

from __future__ import annotations

import pytest
import typer

from neviri_cli.exceptions import (
    AuthError,
    NetworkError,
    NeviriCLIError,
    ServerError,
    UserError,
    handle_cli_error,
)


def test_exit_code_contract() -> None:
    # These numbers are part of the public CLI contract. Changing them
    # is a major-version bump; this test guards that.
    assert NeviriCLIError.exit_code == 1
    assert UserError.exit_code == 2
    assert AuthError.exit_code == 3
    assert NetworkError.exit_code == 4
    assert ServerError.exit_code == 5


def test_message_and_request_id_round_trip() -> None:
    err = AuthError("token expired", request_id="abc-123")
    assert err.message == "token expired"
    assert err.request_id == "abc-123"
    assert str(err) == "token expired"


def test_request_id_optional() -> None:
    err = UserError("missing --name")
    assert err.request_id is None


def test_subclass_chain() -> None:
    assert issubclass(UserError, NeviriCLIError)
    assert issubclass(AuthError, NeviriCLIError)
    assert issubclass(NetworkError, NeviriCLIError)
    assert issubclass(ServerError, NeviriCLIError)


def test_handle_cli_error_raises_typer_exit_with_code(capsys: pytest.CaptureFixture[str]) -> None:
    err = NetworkError("connection refused", request_id="req-9")
    with pytest.raises(typer.Exit) as info:
        handle_cli_error(err)
    assert info.value.exit_code == 4
    captured = capsys.readouterr()
    assert "connection refused" in captured.err
    assert "req-9" in captured.err


def test_handle_cli_error_no_request_id(capsys: pytest.CaptureFixture[str]) -> None:
    err = ServerError("internal error")
    with pytest.raises(typer.Exit) as info:
        handle_cli_error(err)
    assert info.value.exit_code == 5
    captured = capsys.readouterr()
    assert "internal error" in captured.err
    assert "request-id" not in captured.err
