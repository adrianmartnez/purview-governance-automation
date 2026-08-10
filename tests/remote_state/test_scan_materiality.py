"""Unsupported scan configurable materiality: absent/null vs explicit values."""

from __future__ import annotations

from typing import Any

import pytest

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


def test_absent_unsupported_configurables_are_comparable() -> None:
    result = normalize_azure_storage_msi_scan_get(
        _base_scan_body(),
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert result.unsupported_configurable_fields == ()


@pytest.mark.parametrize(
    "field_name",
    [
        "connectedVia",
        "domain",
        "isLiveViewEnabled",
        "isPresetScan",
        "logLevel",
        "parallelScanCount",
        "workers",
        "businessRuleSetName",
    ],
)
def test_null_unsupported_configurables_are_comparable(field_name: str) -> None:
    result = normalize_azure_storage_msi_scan_get(
        _base_scan_body(**{field_name: None}),
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert result.unsupported_configurable_fields == ()


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
    result = normalize_azure_storage_msi_scan_get(
        _base_scan_body(**{field_name: value}),
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert pointer in result.unsupported_configurable_fields


def test_explicit_data_source_identifier_object_is_recorded() -> None:
    body = _base_scan_body()
    body["dataSourceIdentifier"] = {"name": "alphaSource"}
    result = normalize_azure_storage_msi_scan_get(
        body,
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert "/dataSourceIdentifier" in result.unsupported_configurable_fields


def test_unsupported_fields_are_sorted_deterministically() -> None:
    result = normalize_azure_storage_msi_scan_get(
        _base_scan_body(
            workers=1,
            connectedVia={"referenceName": "ir1"},
            isLiveViewEnabled=False,
        ),
        requested_data_source_name="alphaSource",
        requested_scan_name="alphaScan",
    )
    assert result.unsupported_configurable_fields == (
        "/properties/connectedVia",
        "/properties/isLiveViewEnabled",
        "/properties/workers",
    )
