"""Real local HTTP contract tests for Scanning Scan Rule Set operations."""

from __future__ import annotations

import pytest

from purview_governance.scanning import SCANNING_API_VERSION, PurviewHttpError
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import (
    AUTH_SENTINEL,
    custom_azure_storage_scan_ruleset_fixture,
    start_contract_server,
)

AUTH_RAW = AUTH_SENTINEL


@pytest.mark.api_contract
def test_list_scan_rulesets_empty_and_success() -> None:
    with start_contract_server(scan_ruleset_list_mode="empty") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_scan_rule_sets()
        assert result.item_count == 0
        rec = server.state.recordings[0]
        assert rec.method == "GET"
        assert rec.path == "/scan/scanrulesets"
        assert rec.api_version == SCANNING_API_VERSION
        assert rec.authorization_valid is True

    with start_contract_server(scan_ruleset_list_mode="success") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_scan_rule_sets()
        assert result.item_count == 1
        assert result.items[0]["name"] == "custom-rules"


@pytest.mark.api_contract
def test_get_scan_ruleset_success_and_not_found() -> None:
    body = custom_azure_storage_scan_ruleset_fixture("custom-rules")
    with start_contract_server(scan_ruleset_bodies={"custom-rules": body}) as server:
        with make_loopback_client(server.base_url) as client:
            data = client.get_scan_rule_set("custom-rules")
        assert data["name"] == "custom-rules"
        assert data["kind"] == "AzureStorage"
        assert data["scanRulesetType"] == "Custom"
        assert data["properties"]["scanningRule"]["fileExtensions"] == ["CSV", "JSON"]
        rec = server.state.recordings[0]
        assert rec.path == "/scan/scanrulesets/custom-rules"
        assert rec.api_version == SCANNING_API_VERSION

    with (
        start_contract_server(scan_ruleset_get_mode="not_found") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.get_scan_rule_set("missing-rules")
    assert exc.value.status_code == 404
    assert AUTH_RAW not in str(exc.value)


@pytest.mark.api_contract
def test_get_scan_ruleset_official_shaped_custom_file_extensions() -> None:
    """Official ScanningRule shape may include customFileExtensions array."""
    custom = [
        {
            "fileExtension": ".log",
            "description": "plain logs",
            "enabled": True,
            "customFileType": {"builtInType": "TXT"},
        }
    ]
    body = custom_azure_storage_scan_ruleset_fixture(
        "custom-rules",
        custom_file_extensions=custom,
    )
    with start_contract_server(scan_ruleset_bodies={"custom-rules": body}) as server:
        with make_loopback_client(server.base_url) as client:
            data = client.get_scan_rule_set("custom-rules")
        scanning_rule = data["properties"]["scanningRule"]
        assert scanning_rule["fileExtensions"] == ["CSV", "JSON"]
        assert scanning_rule["customFileExtensions"] == custom
        assert "customFileExtensions" in scanning_rule


@pytest.mark.api_contract
def test_list_scan_rulesets_http_error() -> None:
    with (
        start_contract_server(scan_ruleset_list_mode="http_error") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.list_scan_rule_sets()
    assert exc.value.status_code == 503
