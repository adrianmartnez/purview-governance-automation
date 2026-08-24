"""Offline Unified Catalog Data Assets v3 contract tests."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from purview_governance.unified_catalog.constants import DATA_ASSETS_PATH
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_asset_item,
    start_unified_catalog_contract_server,
)

pytestmark = pytest.mark.api_contract

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_enumerate_data_assets_capture() -> None:
    domain = fictional_business_domain_item()
    asset = fictional_data_asset_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_assets_items=[asset],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            state = capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_assets=True,
            )
        finally:
            client.close()

    assert state.includes_data_asset_capture
    assert len(state.data_assets) == 1
    asset_paths = [r.path for r in server.state.recordings if r.path == DATA_ASSETS_PATH]
    assert asset_paths
