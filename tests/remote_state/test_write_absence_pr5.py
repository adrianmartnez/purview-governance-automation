"""PR5 write-absence validation for read-model APIs."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.service import capture_unified_catalog_remote_state_v3
from tests.contract.unified_catalog_client_helpers import make_loopback_unified_catalog_client
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_asset_item,
    fictional_data_column_item,
    start_unified_catalog_contract_server,
)

pytestmark = pytest.mark.api_contract

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_pr5_capture_uses_only_read_apis() -> None:
    domain = fictional_business_domain_item()
    with start_unified_catalog_contract_server(
        enumerate_items=[domain],
        enumerate_data_assets_items=[fictional_data_asset_item()],
        query_data_columns_items=[fictional_data_column_item()],
    ) as server:
        client = make_loopback_unified_catalog_client(server.base_url)
        try:
            capture_unified_catalog_remote_state_v3(
                client,
                tenant_id=TENANT_ID,
                include_data_assets=True,
                include_data_columns=True,
            )
        finally:
            client.close()
        methods = {record.method for record in server.state.recordings}
        assert methods <= {"GET", "POST"}
