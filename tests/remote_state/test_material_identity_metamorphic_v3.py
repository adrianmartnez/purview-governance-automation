"""Material-state identity metamorphic tests for PR5 read models."""

from __future__ import annotations

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.canonical import compute_material_state_identity
from purview_governance.remote_state.data_asset_normalize import normalize_data_asset
from purview_governance.remote_state.data_column_normalize import normalize_data_column
from purview_governance.remote_state.governance_relationship_normalize import (
    normalize_governance_relationship,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedDataAsset,
    NormalizedDataColumn,
    NormalizedGovernanceRelationship,
    ReadModelCoverageV3,
    RemoteTargetContextV3,
    build_remote_state_v3,
)
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ASSET_ID = "60000000-0000-4000-8000-000000000001"
SOURCE_ASSET_ID = "70000000-0000-4000-8000-000000000002"
COLUMN_ID = "80000000-0000-4000-8000-000000000001"
OWNER_A = "30000000-0000-4000-8000-000000000001"
OWNER_B = "30000000-0000-4000-8000-000000000002"
SOURCE_ID = "40000000-0000-4000-8000-000000000001"
TARGET_A = "60000000-0000-4000-8000-000000000001"
TARGET_B = "60000000-0000-4000-8000-000000000002"


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


def _raw_asset(**overrides: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "id": ASSET_ID,
        "name": "sales-table",
        "type": "General",
        "source": {
            "type": "AzureSqlTable",
            "assetId": SOURCE_ASSET_ID,
            "assetType": "AzureSqlTable",
            "fqn": "server.database.schema.table",
            "accountName": "account",
            "assetAttributes": ["a1", "a2"],
        },
        "systemData": {"provisioningState": "Succeeded"},
    }
    raw.update(overrides)
    return raw


def _asset_identity(raw: dict[str, object]) -> str:
    result = normalize_data_asset(raw)
    assert isinstance(result, NormalizedDataAsset)
    state = build_remote_state_v3(
        (),
        (),
        _target(),
        data_assets=(result,),
        uninterpreted_data_assets=(),
        read_model_coverage=ReadModelCoverageV3(data_assets=True),
    )
    return state.material_state_identity


def _column_identity(raw: dict[str, object]) -> str:
    result = normalize_data_column(raw)
    assert isinstance(result, NormalizedDataColumn)
    doc = {"dataColumns": [result.to_document()]}
    return compute_material_state_identity(doc)


def _base_column_raw() -> dict[str, object]:
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


def _relationship_identity(
    edges: tuple[NormalizedGovernanceRelationship, ...],
) -> str:
    state = build_remote_state_v3(
        (),
        (),
        _target(),
        governance_relationships=edges,
        uninterpreted_governance_relationships=(),
        read_model_coverage=ReadModelCoverageV3(
            relationship_data_product_to_data_asset=True,
        ),
    )
    return state.material_state_identity


def test_data_asset_schema_order_changes_material_identity() -> None:
    schema_first = [
        {"name": "col1", "type": "int"},
        {"name": "col2", "type": "varchar"},
    ]
    schema_second = [
        {"name": "col2", "type": "varchar"},
        {"name": "col1", "type": "int"},
    ]
    identity_a = _asset_identity(_raw_asset(schema=schema_first))
    identity_b = _asset_identity(_raw_asset(schema=schema_second))
    assert identity_a != identity_b


def test_data_asset_contact_order_within_role_same_identity() -> None:
    contacts_ab = {
        "owner": [{"id": OWNER_A}, {"id": OWNER_B}],
        "expert": [{"id": OWNER_B}, {"id": OWNER_A}],
        "databaseAdmin": [{"id": OWNER_B}, {"id": OWNER_A}],
    }
    contacts_ba = {
        "owner": [{"id": OWNER_B}, {"id": OWNER_A}],
        "expert": [{"id": OWNER_A}, {"id": OWNER_B}],
        "databaseAdmin": [{"id": OWNER_A}, {"id": OWNER_B}],
    }
    identity_ab = _asset_identity(_raw_asset(contacts=contacts_ab))
    identity_ba = _asset_identity(_raw_asset(contacts=contacts_ba))
    assert identity_ab == identity_ba


def test_data_asset_classification_order_same_identity() -> None:
    identity_ab = _asset_identity(_raw_asset(classifications=["PII", "PHI"]))
    identity_ba = _asset_identity(_raw_asset(classifications=["PHI", "PII"]))
    assert identity_ab == identity_ba


def test_data_asset_schema_classification_order_same_identity() -> None:
    schema_ab = [
        {
            "name": "col1",
            "type": "int",
            "classifications": ["PII", "PHI"],
        }
    ]
    schema_ba = [
        {
            "name": "col1",
            "type": "int",
            "classifications": ["PHI", "PII"],
        }
    ]
    identity_ab = _asset_identity(_raw_asset(schema=schema_ab))
    identity_ba = _asset_identity(_raw_asset(schema=schema_ba))
    assert identity_ab == identity_ba


def test_governance_relationship_input_order_same_identity() -> None:
    edge_a = normalize_governance_relationship(
        {"entityId": TARGET_A, "relationshipType": "Related"},
        source_type="dataProduct",
        source_id=SOURCE_ID,
        target_category="DATAASSET",
    )
    edge_b = normalize_governance_relationship(
        {"entityId": TARGET_B, "relationshipType": "Related"},
        source_type="dataProduct",
        source_id=SOURCE_ID,
        target_category="DATAASSET",
    )
    assert isinstance(edge_a, NormalizedGovernanceRelationship)
    assert isinstance(edge_b, NormalizedGovernanceRelationship)
    identity_ab = _relationship_identity((edge_a, edge_b))
    identity_ba = _relationship_identity((edge_b, edge_a))
    assert identity_ab == identity_ba


def test_governance_relationship_system_data_only_same_identity() -> None:
    system_data_old = {
        "createdAt": "legacy-timestamp-string",
        "createdBy": "00000000-0000-0000-0000-000000000001",
        "lastModifiedAt": "1970-01-01T00:00:00.000Z",
        "lastModifiedBy": "00000000-0000-0000-0000-000000000001",
    }
    system_data_new = {
        "createdAt": "another-arbitrary-string",
        "createdBy": "11111111-1111-1111-1111-111111111111",
        "lastModifiedAt": "2020-01-01T00:00:00.000Z",
        "lastModifiedBy": "22222222-2222-2222-2222-222222222222",
    }
    edge_old = normalize_governance_relationship(
        {
            "entityId": TARGET_A,
            "relationshipType": "Related",
            "description": "stable edge",
            "systemData": system_data_old,
        },
        source_type="dataProduct",
        source_id=SOURCE_ID,
        target_category="DATAASSET",
    )
    edge_new = normalize_governance_relationship(
        {
            "entityId": TARGET_A,
            "relationshipType": "Related",
            "description": "stable edge",
            "systemData": system_data_new,
        },
        source_type="dataProduct",
        source_id=SOURCE_ID,
        target_category="DATAASSET",
    )
    assert isinstance(edge_old, NormalizedGovernanceRelationship)
    assert isinstance(edge_new, NormalizedGovernanceRelationship)
    assert edge_old.to_document() == edge_new.to_document()
    assert _relationship_identity((edge_old,)) == _relationship_identity((edge_new,))


def test_column_details_absent_vs_null_distinct_identity() -> None:
    absent = _base_column_raw()
    with_null = dict(_base_column_raw())
    with_null["columnDetails"] = None
    assert _column_identity(absent) != _column_identity(with_null)


def test_asset_details_absent_vs_null_distinct_identity() -> None:
    absent = _base_column_raw()
    with_null = dict(_base_column_raw())
    with_null["assetDetails"] = None
    assert _column_identity(absent) != _column_identity(with_null)
