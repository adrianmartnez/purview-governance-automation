"""Tests for Scanning API date-time validation helper."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.api_datetime import validate_api_datetime_string


def test_official_sample_with_z_and_long_fraction() -> None:
    raw = "2019-12-09T06:43:30.8478469Z"
    assert validate_api_datetime_string(raw) == raw


def test_offset_timezone_accepted() -> None:
    raw = "2019-12-09T06:43:30.847846+00:00"
    assert validate_api_datetime_string(raw) == raw


def test_rejects_naive_and_malformed() -> None:
    with pytest.raises(ValueError):
        validate_api_datetime_string("2019-12-09T06:43:30.8478469")
    with pytest.raises(ValueError):
        validate_api_datetime_string("not-a-date")
    with pytest.raises(ValueError):
        validate_api_datetime_string(None)
    with pytest.raises(ValueError):
        validate_api_datetime_string("")
