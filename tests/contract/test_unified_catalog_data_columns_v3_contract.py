"""Offline Unified Catalog Data Columns v3 contract tests."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.constants import (
    DATA_COLUMN_QUERY_PAGE_SIZE,
    DATA_COLUMNS_QUERY_PATH,
)
from purview_governance.unified_catalog.errors import (
    UnifiedCatalogPaginationError,
    UnifiedCatalogResponseError,
)
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_column_item,
    start_unified_catalog_contract_server,
)

pytestmark = pytest.mark.api_contract

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DUPLICATE_COLUMN_ID = "80000000-0000-4000-8000-000000000001"


def _full_page_columns(count: int = DATA_COLUMN_QUERY_PAGE_SIZE) -> list[dict[str, object]]:
    return [
        fictional_data_column_item(
            column_id=f"10000000-0000-4000-8000-{index:012x}",
            name=f"column-{index}",
        )
        for index in range(count)
    ]


def _assert_column_query_post_only(server: object) -> None:
    recordings = server.state.recordings
    assert recordings
    assert all(record.method == "POST" for record in recordings)
    assert all(record.method != "GET" for record in recordings)
    assert all(record.path == DATA_COLUMNS_QUERY_PATH for record in recordings)


def _assert_query_body_flags(body: dict[str, object]) -> None:
    assert body["includingOrphans"] is True
    assert body["includeColumnDetails"] is True
    assert body["includeAssetDetails"] is True
    assert body["top"] == DATA_COLUMN_QUERY_PAGE_SIZE


def test_query_data_columns_capture_with_next_link() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        query_data_columns_items=[fictional_data_column_item()],
        query_data_columns_page2_items=[
            fictional_data_column_item(
                column_id="eeeeeeee-bbbb-cccc-dddd-eeeeeeeeeeee",
                name="column-two",
            )
        ],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_columns=True,
            )
        finally:
            client.close()

    assert state.includes_data_column_capture
    assert len(state.data_columns) == 2
    post_paths = [r.path for r in server.state.recordings if r.method == "POST"]
    assert post_paths[0] == DATA_COLUMNS_QUERY_PATH


def test_query_data_columns_partial_page_with_next_link_continues() -> None:
    with start_unified_catalog_contract_server(
        enumerate_items=[fictional_business_domain_item()],
        query_data_columns_items=[fictional_data_column_item()],
        query_data_columns_page2_items=[
            fictional_data_column_item(
                column_id="eeeeeeee-bbbb-cccc-dddd-eeeeeeeeeeee",
                name="column-two",
            )
        ],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            result = client.query_data_columns()
        finally:
            client.close()

    assert result.item_count == 2
    _assert_column_query_post_only(server)
    assert len(server.state.column_query_requests) == 2
    _assert_query_body_flags(server.state.column_query_requests[0])
    _assert_query_body_flags(server.state.column_query_requests[1])
    assert server.state.column_query_requests[0]["skip"] == 0
    assert server.state.column_query_requests[1]["skip"] == 1


def test_query_data_columns_empty_page_with_next_link_fail_closed() -> None:
    with start_unified_catalog_contract_server(
        enumerate_items=[fictional_business_domain_item()],
        query_data_columns_mode="empty_next_link",
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            with pytest.raises(UnifiedCatalogPaginationError):
                client.query_data_columns()
        finally:
            client.close()

    _assert_column_query_post_only(server)
    assert len(server.state.column_query_requests) == 1


def test_query_data_columns_foreign_next_link_fail_closed() -> None:
    with start_unified_catalog_contract_server(
        enumerate_items=[fictional_business_domain_item()],
        query_data_columns_mode="foreign_next_link",
        cross_origin_next_link="https://evil.example/continue",
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            with pytest.raises(UnifiedCatalogPaginationError):
                client.query_data_columns()
        finally:
            client.close()

    _assert_column_query_post_only(server)
    assert len(server.state.column_query_requests) == 1


def test_query_data_columns_malformed_next_link_fail_closed() -> None:
    with start_unified_catalog_contract_server(
        enumerate_items=[fictional_business_domain_item()],
        query_data_columns_mode="malformed_next_link",
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            with pytest.raises(UnifiedCatalogResponseError):
                client.query_data_columns()
        finally:
            client.close()

    _assert_column_query_post_only(server)
    assert len(server.state.column_query_requests) == 1


def test_query_data_columns_duplicate_id_cross_page_fail_closed() -> None:
    duplicate_item = fictional_data_column_item(column_id=DUPLICATE_COLUMN_ID)
    with start_unified_catalog_contract_server(
        enumerate_items=[fictional_business_domain_item()],
        query_data_columns_items=[duplicate_item],
        query_data_columns_page2_items=[duplicate_item],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            with pytest.raises(UnifiedCatalogPaginationError):
                client.query_data_columns()
        finally:
            client.close()

    _assert_column_query_post_only(server)
    assert len(server.state.column_query_requests) == 2


def test_query_data_columns_full_page_extra_post_completes_on_empty() -> None:
    with start_unified_catalog_contract_server(
        enumerate_items=[fictional_business_domain_item()],
        query_data_columns_mode="full_page",
        query_data_columns_items=_full_page_columns(),
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            result = client.query_data_columns()
        finally:
            client.close()

    assert result.item_count == DATA_COLUMN_QUERY_PAGE_SIZE
    _assert_column_query_post_only(server)
    assert len(server.state.column_query_requests) == 2
    _assert_query_body_flags(server.state.column_query_requests[0])
    _assert_query_body_flags(server.state.column_query_requests[1])
    assert server.state.column_query_requests[0]["skip"] == 0
    assert server.state.column_query_requests[1]["skip"] == DATA_COLUMN_QUERY_PAGE_SIZE
