"""Microsoft Purview dataSourceName validation (Scanning Data Plane contract)."""

from __future__ import annotations

import re

from purview_governance.scanning.errors import PurviewDataSourceNameError

# Official URI parameter constraints (API 2023-09-01):
# minLength: 3, maxLength: 63, pattern: ^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$
_DATA_SOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")
_MIN_LENGTH = 3
_MAX_LENGTH = 63


def validate_data_source_name(name: object) -> str:
    """Validate ``dataSourceName`` before path construction.

    Raises:
        PurviewDataSourceNameError: when the name is not a str matching the
            official length and pattern constraints.
    """
    if not isinstance(name, str):
        raise PurviewDataSourceNameError(
            "scanning.invalid_data_source_name",
            "dataSourceName must be a string",
        )
    if len(name) < _MIN_LENGTH or len(name) > _MAX_LENGTH:
        raise PurviewDataSourceNameError(
            "scanning.invalid_data_source_name",
            "dataSourceName length must be between 3 and 63 characters",
        )
    if _DATA_SOURCE_NAME_RE.fullmatch(name) is None:
        raise PurviewDataSourceNameError(
            "scanning.invalid_data_source_name",
            "dataSourceName does not match the Microsoft Purview naming pattern",
        )
    return name
