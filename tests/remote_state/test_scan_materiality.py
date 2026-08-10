"""Unsupported scan configurable materiality: null policy + valueIdentity."""

from __future__ import annotations

from typing import Any

import pytest

from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    UnsupportedConfigurableField,
    build_remote_state_v2,
)
from purview_governance.remote_state.normalize import reject_sensitive_keys
from purview_governance.remote_state.scan_normalize import (
    normalize_azure_storage_msi_scan_get,
)


def _base_scan_body(**property_overrides: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "scanRulesetName": "AzureStorage",
        "scanRulesetType": "System",
        "collection": {
            "referenceName": "Collection-rZX",
            "type": "CollectionReference",
        },
    }
    properties.update(property_overrides)
    return {
        "name": "alphaScan",
        "dataSourceName": "alphaSource",
        "kind": "AzureStorageMsi",
        "creationType": "Manual",
        "properties": properties,
    }


def _unsupported_paths(
    fields: tuple[UnsupportedConfigurableField, ...],
) -> tuple[str, ...]:
    return tuple(item.path for item in fields)


def _normalize(**property_overrides: Any):
    return normalize_azure_storage_msi_scan_get(
        _base_scan_body(**property_overrides),
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )


def test_absent_unsupported_configurables_are_comparable() -> None:
    result = _normalize()
    assert result.unsupported_configurable_fields == ()


@pytest.mark.parametrize(
    "field_name",
    [
        "connectedVia",
        "domain",
        "logLevel",
        "businessRuleSetName",
    ],
)
def test_null_safe_absent_unsupported_configurables_are_comparable(field_name: str) -> None:
    result = _normalize(**{field_name: None})
    assert result.unsupported_configurable_fields == ()


@pytest.mark.parametrize(
    "field_name",
    [
        "isLiveViewEnabled",
        "isPresetScan",
        "parallelScanCount",
        "workers",
    ],
)
def test_null_on_boolean_or_int_unsupported_fails(field_name: str) -> None:
    with pytest.raises(RemoteStateError) as exc:
        _normalize(**{field_name: None})
    assert exc.value.code == "remote_state.invalid_shape"
    assert field_name in exc.value.path


def test_null_data_source_identifier_is_comparable() -> None:
    body = _base_scan_body()
    body["dataSourceIdentifier"] = None
    result = normalize_azure_storage_msi_scan_get(
        body,
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert result.unsupported_configurable_fields == ()


@pytest.mark.parametrize(
    ("field_name", "value", "pointer"),
    [
        ("connectedVia", {"referenceName": "ir1"}, "/properties/connectedVia"),
        ("domain", "", "/properties/domain"),
        ("domain", "domainName", "/properties/domain"),
        ("isLiveViewEnabled", False, "/properties/isLiveViewEnabled"),
        ("isLiveViewEnabled", True, "/properties/isLiveViewEnabled"),
        ("isPresetScan", False, "/properties/isPresetScan"),
        ("isPresetScan", True, "/properties/isPresetScan"),
        ("logLevel", "", "/properties/logLevel"),
        ("logLevel", "Info", "/properties/logLevel"),
        ("parallelScanCount", 0, "/properties/parallelScanCount"),
        ("parallelScanCount", 2, "/properties/parallelScanCount"),
        ("workers", 0, "/properties/workers"),
        ("workers", 4, "/properties/workers"),
        ("businessRuleSetName", "", "/properties/businessRuleSetName"),
        ("businessRuleSetName", "rules", "/properties/businessRuleSetName"),
    ],
)
def test_explicit_unsupported_configurables_are_recorded(
    field_name: str,
    value: object,
    pointer: str,
) -> None:
    result = _normalize(**{field_name: value})
    assert pointer in _unsupported_paths(result.unsupported_configurable_fields)
    match = next(item for item in result.unsupported_configurable_fields if item.path == pointer)
    assert match.value_identity == compute_value_identity(value)


def test_explicit_data_source_identifier_object_is_recorded() -> None:
    body = _base_scan_body()
    body["dataSourceIdentifier"] = {"name": "alphaSource"}
    result = normalize_azure_storage_msi_scan_get(
        body,
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert "/dataSourceIdentifier" in _unsupported_paths(result.unsupported_configurable_fields)


def test_unsupported_fields_are_sorted_deterministically() -> None:
    result = _normalize(
        workers=1,
        connectedVia={"referenceName": "ir1"},
        isLiveViewEnabled=False,
    )
    assert _unsupported_paths(result.unsupported_configurable_fields) == (
        "/properties/connectedVia",
        "/properties/isLiveViewEnabled",
        "/properties/workers",
    )


def test_malformed_string_for_boolean_fails() -> None:
    with pytest.raises(RemoteStateError) as exc:
        _normalize(isLiveViewEnabled="yes")
    assert exc.value.code == "remote_state.invalid_shape"


def test_malformed_bool_for_integer_fails() -> None:
    with pytest.raises(RemoteStateError) as exc:
        _normalize(parallelScanCount=True)
    assert exc.value.code == "remote_state.invalid_shape"


def _remote_identity_for_scan(**property_overrides: Any) -> str:
    scan = _normalize(**property_overrides)
    state = build_remote_state_v2((), (), (scan,), (), (), ())
    return state.material_state_identity


def test_is_live_view_enabled_false_vs_true_differ_material_identity() -> None:
    assert _remote_identity_for_scan(isLiveViewEnabled=False) != _remote_identity_for_scan(
        isLiveViewEnabled=True
    )


def test_parallel_scan_count_zero_vs_positive_differ_material_identity() -> None:
    assert _remote_identity_for_scan(parallelScanCount=0) != _remote_identity_for_scan(
        parallelScanCount=2
    )


def test_connected_via_object_a_vs_b_differ_material_identity() -> None:
    assert _remote_identity_for_scan(connectedVia={"referenceName": "ir-a"}) != (
        _remote_identity_for_scan(connectedVia={"referenceName": "ir-b"})
    )


def test_equivalent_object_different_key_order_same_value_and_material_identity() -> None:
    a = {"referenceName": "ir1", "type": "IntegrationRuntimeReference"}
    b = {"type": "IntegrationRuntimeReference", "referenceName": "ir1"}
    result_a = _normalize(connectedVia=a)
    result_b = _normalize(connectedVia=b)
    assert result_a.unsupported_configurable_fields[0].value_identity == (
        result_b.unsupported_configurable_fields[0].value_identity
    )
    state_a = build_remote_state_v2((), (), (result_a,), (), (), ())
    state_b = build_remote_state_v2((), (), (result_b,), (), (), ())
    assert state_a.material_state_identity == state_b.material_state_identity


def test_sensitive_keys_rejected_before_unsupported_capture() -> None:
    with pytest.raises(RemoteStateError) as exc:
        _normalize(connectedVia={"referenceName": "ir1", "password": "secret"})
    assert exc.value.code == "remote_state.sensitive_field"


def test_reject_sensitive_keys_on_value_subtree_helper() -> None:
    value = {"referenceName": "ir1", "clientSecret": "x"}
    with pytest.raises(RemoteStateError) as exc:
        reject_sensitive_keys(value, path_parts=("properties", "connectedVia"))
    assert exc.value.code == "remote_state.sensitive_field"
