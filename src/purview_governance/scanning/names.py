"""Microsoft Purview resource name validation (Scanning Data Plane contract)."""

from __future__ import annotations

import re

from purview_governance.scanning.errors import PurviewDataSourceNameError

# Official URI parameter constraints (API 2023-09-01):
# minLength: 3, maxLength: 63, pattern: ^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$
_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")
_MIN_LENGTH = 3
_MAX_LENGTH = 63


def _validate_named_resource(name: object, *, field_name: str, code: str) -> str:
    if not isinstance(name, str):
        raise PurviewDataSourceNameError(code, f"{field_name} must be a string")
    if len(name) < _MIN_LENGTH or len(name) > _MAX_LENGTH:
        raise PurviewDataSourceNameError(
            code,
            f"{field_name} length must be between 3 and 63 characters",
        )
    if _NAME_RE.fullmatch(name) is None:
        raise PurviewDataSourceNameError(
            code,
            f"{field_name} does not match the Microsoft Purview naming pattern",
        )
    return name


def validate_data_source_name(name: object) -> str:
    """Validate ``dataSourceName`` before path construction."""
    return _validate_named_resource(
        name,
        field_name="dataSourceName",
        code="scanning.invalid_data_source_name",
    )


def validate_scan_name(name: object) -> str:
    """Validate ``scanName`` before path construction."""
    return _validate_named_resource(
        name,
        field_name="scanName",
        code="scanning.invalid_scan_name",
    )


def validate_scan_ruleset_name(name: object) -> str:
    """Validate ``scanRulesetName`` before path construction."""
    return _validate_named_resource(
        name,
        field_name="scanRulesetName",
        code="scanning.invalid_scan_ruleset_name",
    )


def validate_classification_rule_name(name: object) -> str:
    """Validate ``classificationRuleName`` before path construction."""
    return _validate_named_resource(
        name,
        field_name="classificationRuleName",
        code="scanning.invalid_classification_rule_name",
    )
