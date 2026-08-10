"""Real local HTTP contract tests for Scanning Scan operations."""

from __future__ import annotations

import pytest

from purview_governance.scanning import SCANNING_API_VERSION, PurviewHttpError
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import (
    AUTH_SENTINEL,
    azure_storage_msi_scan_fixture,
    start_contract_server,
)

AUTH_RAW = AUTH_SENTINEL


@pytest.mark.api_contract
def test_list_scans_empty_and_success() -> None:
    with start_contract_server(scan_list_mode="empty") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_scans("alphaSource")
        assert result.item_count == 0
        rec = server.state.recordings[0]
        assert rec.method == "GET"
        assert rec.path == "/scan/datasources/alphaSource/scans"
        assert rec.api_version == SCANNING_API_VERSION
        assert rec.authorization_valid is True
        assert AUTH_RAW not in str(rec)

    with start_contract_server(scan_list_mode="success") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_scans("alphaSource")
        assert result.item_count == 1
        assert result.items[0]["name"] == "alphaScan"


@pytest.mark.api_contract
def test_get_scan_success_and_not_found() -> None:
    body = azure_storage_msi_scan_fixture("alphaScan", data_source_name="alphaSource")
    with start_contract_server(
        scan_bodies={("alphaSource", "alphaScan"): body},
    ) as server:
        with make_loopback_client(server.base_url) as client:
            data = client.get_scan("alphaSource", "alphaScan")
        assert data["name"] == "alphaScan"
        assert data["kind"] == "AzureStorageMsi"
        assert data["properties"]["scanRulesetName"] == "AzureStorage"
        rec = server.state.recordings[0]
        assert rec.path == "/scan/datasources/alphaSource/scans/alphaScan"
        assert rec.api_version == SCANNING_API_VERSION

    with (
        start_contract_server(scan_get_mode="not_found") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.get_scan("alphaSource", "missingScan")
    assert exc.value.status_code == 404
    assert AUTH_RAW not in str(exc.value)


@pytest.mark.api_contract
def test_list_scans_http_error() -> None:
    with (
        start_contract_server(scan_list_mode="http_error") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.list_scans("alphaSource")
    assert exc.value.status_code == 503
