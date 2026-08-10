"""Capture v2 must not list scans under unsupported Data Source parents."""

from __future__ import annotations

from purview_governance.remote_state import capture_remote_state_v2
from tests.contract.server import azure_storage_fixture
from tests.remote_state.fakes import FakeScanningReadClient


def _azure_storage_msi_scan_fixture(
    *,
    scan_name: str,
    data_source_name: str,
) -> dict[str, object]:
    return {
        "name": scan_name,
        "dataSourceName": data_source_name,
        "kind": "AzureStorageMsi",
        "creationType": "Manual",
        "properties": {
            "scanRulesetName": "AzureStorage",
            "scanRulesetType": "System",
            "collection": {
                "referenceName": "Collection-rZX",
                "type": "CollectionReference",
            },
        },
    }


def test_unsupported_parent_does_not_call_list_scans() -> None:
    client = FakeScanningReadClient(
        list_items=[
            {"name": "alphaSource"},
            {"name": "otherSource"},
        ],
        get_bodies={
            "alphaSource": azure_storage_fixture("alphaSource"),
            "otherSource": {
                "name": "otherSource",
                "kind": "AdlsGen2",
                "creationType": "Manual",
                "properties": {
                    "endpoint": "https://datalake.dfs.core.windows.net/",
                    "collection": {"referenceName": "root"},
                    "dataSourceCollectionMovingState": "Active",
                },
            },
        },
        scan_list_by_parent={
            "alphaSource": [{"name": "alphaScan"}],
            # If capture incorrectly lists under unsupported parent, this would be used.
            "otherSource": [{"name": "shouldNotList"}],
        },
        scan_get_bodies={
            ("alphaSource", "alphaScan"): _azure_storage_msi_scan_fixture(
                scan_name="alphaScan",
                data_source_name="alphaSource",
            ),
        },
        scan_ruleset_list_items=[],
        scan_ruleset_get_bodies={},
    )

    state = capture_remote_state_v2(client)

    assert [ds.name for ds in state.data_sources] == ["alphaSource"]
    assert [ui.name for ui in state.uninterpreted_data_sources] == ["otherSource"]
    assert client.list_scan_calls == ["alphaSource"]
    assert "otherSource" not in client.list_scan_calls
    assert client.get_scan_calls == [("alphaSource", "alphaScan")]
    assert [scan.name for scan in state.scans] == ["alphaScan"]
    assert state.uninterpreted_scans == ()
