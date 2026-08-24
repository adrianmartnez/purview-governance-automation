"""Data Asset remote-state v3 normalization tests."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.data_asset_normalize import normalize_data_asset
from purview_governance.remote_state.data_asset_policy import (
    DATA_ASSET_TYPES,
    REASON_UNSUPPORTED_TYPE,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedDataAsset,
    ReadModelCoverageV3,
    RemoteTargetContextV3,
    UninterpretedDataAsset,
    build_remote_state_v3,
)
from purview_governance.remote_state.schema import load_remote_state_v3_schema
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ASSET_ID = "60000000-0000-4000-8000-000000000001"
SOURCE_ASSET_ID = "70000000-0000-4000-8000-000000000002"


def _target() -> RemoteTargetContextV3:
    endpoint = UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=TENANT,
        endpoint=endpoint,
        identity=compute_target_context_identity_v3(
            surface="unifiedCatalog",
            tenant_id=TENANT,
            endpoint=endpoint,
        ),
    )


def _raw_asset(*, asset_type: str = "General") -> dict[str, object]:
    return {
        "id": ASSET_ID,
        "name": "sales-table",
        "type": asset_type,
        "source": {
            "type": "AzureSqlTable",
            "assetId": SOURCE_ASSET_ID,
            "assetType": "AzureSqlTable",
            "fqn": "server.database.schema.table",
            "accountName": "account",
            "assetAttributes": ["a1", "a2"],
        },
        "systemData": {
            "provisioningState": "Succeeded",
        },
    }


@pytest.mark.parametrize("asset_type", sorted(DATA_ASSET_TYPES))
def test_normalize_all_official_data_asset_types(asset_type: str) -> None:
    raw = _raw_asset(asset_type=asset_type)
    if asset_type in {"AzureSqlTable", "ADLSGen2Path"}:
        if asset_type == "AzureSqlTable":
            raw["typeProperties"] = {
                "format": "Table",
                "serverEndpoint": "sql.example",
                "databaseName": "db",
                "schemaName": "schema",
                "tableName": "table",
            }
        else:
            raw["typeProperties"] = {
                "serverEndpoint": "storage.example",
                "container": "container",
                "folderPath": "folder",
                "fileName": "file",
            }
    result = normalize_data_asset(raw)
    assert isinstance(result, NormalizedDataAsset)
    assert result.fields["assetType"] == asset_type


def test_normalize_unknown_type_is_uninterpreted() -> None:
    result = normalize_data_asset(_raw_asset(asset_type="Unsupported"))
    assert isinstance(result, UninterpretedDataAsset)
    assert result.reason_code == REASON_UNSUPPORTED_TYPE


def test_asset_id_and_source_asset_id_remain_distinct() -> None:
    result = normalize_data_asset(_raw_asset())
    assert isinstance(result, NormalizedDataAsset)
    doc = result.to_document()
    assert doc["id"] == ASSET_ID
    assert doc["source"]["assetId"] == SOURCE_ASSET_ID


def test_normalized_data_asset_validates_against_schema() -> None:
    result = normalize_data_asset(_raw_asset())
    assert isinstance(result, NormalizedDataAsset)
    state = build_remote_state_v3(
        (),
        (),
        _target(),
        data_assets=(result,),
        uninterpreted_data_assets=(),
        read_model_coverage=ReadModelCoverageV3(data_assets=True),
    )
    validator = Draft202012Validator(load_remote_state_v3_schema())
    errors = list(validator.iter_errors(state.to_document()))
    assert not errors
