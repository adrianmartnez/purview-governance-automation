"""Data Column remote-state v3 normalization tests."""

from __future__ import annotations

from purview_governance.remote_state.data_column_normalize import normalize_data_column
from purview_governance.remote_state.models_v3 import NormalizedDataColumn

COLUMN_ID = "80000000-0000-4000-8000-000000000001"


def _base_raw() -> dict[str, object]:
    return {
        "id": COLUMN_ID,
        "name": "column-a",
        "type": "General",
        "source": {
            "type": "AzureSqlColumn",
            "assetId": "70000000-0000-4000-8000-000000000001",
            "columnId": "90000000-0000-4000-8000-000000000001",
            "assetType": "AzureSqlTable",
            "fqn": "server.database.schema.table.column",
            "accountName": "account",
            "assetAttributes": ["a1"],
        },
    }


def test_asset_details_asset_id_preserved_as_string() -> None:
    raw = _base_raw()
    raw["assetDetails"] = {"assetId": "DG-STRING-NOT-UUID", "name": "parent"}
    result = normalize_data_column(raw)
    assert isinstance(result, NormalizedDataColumn)
    assert result.fields["assetDetails"]["assetId"] == "DG-STRING-NOT-UUID"
