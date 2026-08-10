"""Real local HTTP contract tests for Scanning Data Source operations."""

from __future__ import annotations

import json

import pytest

from purview_governance.scanning import (
    SCANNING_API_VERSION,
    PurviewHttpError,
    PurviewPaginationError,
    PurviewResponseError,
)
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import AUTH_SENTINEL, start_contract_server

AUTH_RAW = AUTH_SENTINEL


def _assert_recording_has_no_raw_authorization(server) -> None:
    blob = json.dumps(
        [
            {
                "method": r.method,
                "path": r.path,
                "api_version": r.api_version,
                "accept": r.accept,
                "content_type": r.content_type,
                "authorization_present": r.authorization_present,
                "authorization_valid": r.authorization_valid,
                "json_body": r.json_body,
            }
            for r in server.state.recordings
        ]
    )
    assert AUTH_RAW not in blob
    assert "TEST_PURVIEW_AUTH_SENTINEL" not in blob


@pytest.mark.api_contract
def test_list_one_page_contract() -> None:
    with start_contract_server(list_mode="one_page") as server:
        with make_loopback_client(server.base_url) as client:
            assert client.trust_env is False
            result = client.list_data_sources()
        assert result.item_count == 1
        assert result.items[0]["name"] == "alphaSource"
        assert len(server.state.recordings) == 1
        rec = server.state.recordings[0]
        assert rec.method == "GET"
        assert rec.path == "/scan/datasources"
        assert rec.api_version == SCANNING_API_VERSION
        assert rec.accept == "application/json"
        assert rec.authorization_present is True
        assert rec.authorization_valid is True
        _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_list_paginated_aggregate_without_summing_count() -> None:
    with start_contract_server(list_mode="paginated") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_data_sources()
        assert [item["name"] for item in result.items] == ["alphaSource", "betaSource"]
        assert result.item_count == 2
        assert result.item_count != 99 + 1
        assert len(server.state.recordings) == 2
        assert all(r.authorization_valid for r in server.state.recordings)
        _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_get_success_and_not_found() -> None:
    with start_contract_server(get_mode="success") as server:
        with make_loopback_client(server.base_url) as client:
            data = client.get_data_source("myDataSource")
        assert data["name"] == "myDataSource"
        rec = server.state.recordings[0]
        assert rec.method == "GET"
        assert rec.path == "/scan/datasources/myDataSource"
        assert rec.api_version == SCANNING_API_VERSION
        assert rec.authorization_valid is True

    with (
        start_contract_server(get_mode="not_found") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.get_data_source("missingSource")
    assert exc.value.status_code == 404
    assert AUTH_RAW not in str(exc.value)


@pytest.mark.api_contract
def test_put_create_or_replace_canonical_body() -> None:
    payload = {
        "kind": "AzureStorage",
        "properties": {"endpoint": "https://example.blob.core.windows.net/"},
    }
    with start_contract_server(put_mode="created", put_expected_body=payload) as server:
        with make_loopback_client(server.base_url) as client:
            result = client._create_or_replace_data_source("myDataSource", payload)
        assert result.name == "myDataSource"
        assert result.status_code == 201
        rec = server.state.recordings[0]
        assert rec.method == "PUT"
        assert rec.path == "/scan/datasources/myDataSource"
        assert rec.api_version == SCANNING_API_VERSION
        assert rec.content_type == "application/json"
        assert rec.authorization_valid is True
        assert rec.json_body == payload
        _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_put_accepts_200_ok() -> None:
    payload = {"kind": "AzureStorage"}
    with start_contract_server(put_mode="ok", put_expected_body=payload) as server:
        with make_loopback_client(server.base_url) as client:
            result = client._create_or_replace_data_source("myDataSource", payload)
        assert result.name == "myDataSource"
        assert result.status_code == 200


@pytest.mark.api_contract
def test_put_bad_json_body_still_confirmed_write() -> None:
    payload = {"kind": "AzureStorage"}
    with start_contract_server(put_mode="ok_bad_json", put_expected_body=payload) as server:
        with make_loopback_client(server.base_url) as client:
            result = client._create_or_replace_data_source("myDataSource", payload)
        assert result.status_code == 200
        assert len([r for r in server.state.recordings if r.method == "PUT"]) == 1


@pytest.mark.api_contract
def test_cross_origin_next_link_no_second_request() -> None:
    with (
        start_contract_server(list_mode="cross_origin") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewPaginationError),
    ):
        client.list_data_sources()
    assert len(server.state.recordings) == 1
    _assert_recording_has_no_raw_authorization(server)


@pytest.mark.api_contract
def test_relative_next_link_rejected() -> None:
    with (
        start_contract_server(list_mode="relative_next") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewPaginationError),
    ):
        client.list_data_sources()
    assert len(server.state.recordings) == 1


@pytest.mark.api_contract
def test_loop_next_link_rejected() -> None:
    with (
        start_contract_server(list_mode="loop_next") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewPaginationError) as exc,
    ):
        client.list_data_sources()
    assert exc.value.code == "scanning.pagination_loop"
    # First page + one follow that repeats the same nextLink, then reject.
    assert len(server.state.recordings) == 2


@pytest.mark.api_contract
def test_malformed_json_and_bad_shape() -> None:
    with (
        start_contract_server(list_mode="bad_json") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewResponseError),
    ):
        client.list_data_sources()

    with (
        start_contract_server(list_mode="bad_shape") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewResponseError),
    ):
        client.list_data_sources()

    with (
        start_contract_server(get_mode="bad_shape") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewResponseError),
    ):
        client.get_data_source("myDataSource")


@pytest.mark.api_contract
def test_representative_http_error() -> None:
    with (
        start_contract_server(list_mode="http_error") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.list_data_sources()
    assert exc.value.status_code == 503
    assert AUTH_RAW not in repr(exc.value)


@pytest.mark.api_contract
def test_no_purview_azure_com_host_in_recordings() -> None:
    with start_contract_server(list_mode="one_page") as server:
        with make_loopback_client(server.base_url) as client:
            client.list_data_sources()
        assert server.host == "127.0.0.1"
        for rec in server.state.recordings:
            assert "purview.azure.com" not in rec.path
