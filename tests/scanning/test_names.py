"""Tests for dataSourceName validation."""

from __future__ import annotations

import pytest

from purview_governance.scanning.errors import PurviewDataSourceNameError
from purview_governance.scanning.names import validate_data_source_name


@pytest.mark.parametrize(
    "name",
    [
        "abc",
        "myDataSource",
        "Azure-Storage-01",
        "a" * 63,
    ],
)
def test_valid_data_source_names(name: str) -> None:
    assert validate_data_source_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "ab",
        "a" * 64,
        "-leading",
        "trailing-",
        "has_underscore",
        "has.dot",
        "has/slash",
        "../escape",
        "space name",
        "",
        123,
        None,
    ],
)
def test_invalid_data_source_names(name: object) -> None:
    with pytest.raises(PurviewDataSourceNameError) as exc_info:
        validate_data_source_name(name)
    assert exc_info.value.code == "scanning.invalid_data_source_name"
