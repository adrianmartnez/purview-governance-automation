"""Secret-sentinel tests for sanitized authentication failures."""

from __future__ import annotations

import logging
import traceback

import pytest

from purview_governance.auth import AuthenticationError, PurviewAuthorizationProvider
from tests.auth.fakes import FakeTokenCredential

SECRET_SENTINEL = "SECRET_SENTINEL_do-not-leak-auth-material-9f3c"


def test_acquisition_failure_sanitized_and_unlinked() -> None:
    fake = FakeTokenCredential(fail_with=RuntimeError(f"azure boom {SECRET_SENTINEL}"))
    provider = PurviewAuthorizationProvider(fake)  # type: ignore[arg-type]

    with pytest.raises(AuthenticationError) as exc_info:
        provider.acquire_authorization_header()

    error = exc_info.value
    assert error.code == "auth.token_acquisition_failed"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert SECRET_SENTINEL not in str(error)
    assert SECRET_SENTINEL not in repr(error)
    assert SECRET_SENTINEL not in "".join(traceback.format_exception(error))
    assert not any(
        value is not None and SECRET_SENTINEL in str(value) for name, value in vars(error).items()
    )


def test_failure_does_not_leak_to_logs_or_stdio(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeTokenCredential(fail_with=RuntimeError(SECRET_SENTINEL))
    provider = PurviewAuthorizationProvider(fake)  # type: ignore[arg-type]

    with caplog.at_level(logging.DEBUG), pytest.raises(AuthenticationError):
        provider.acquire_authorization_header()

    captured = capsys.readouterr()
    assert SECRET_SENTINEL not in captured.out
    assert SECRET_SENTINEL not in captured.err
    assert SECRET_SENTINEL not in caplog.text
