"""Governance relationship remote-state v3 normalization tests."""

from __future__ import annotations

from purview_governance.remote_state.governance_relationship_normalize import (
    normalize_governance_relationship,
)
from purview_governance.remote_state.models_v3 import NormalizedGovernanceRelationship

SOURCE_ID = "40000000-0000-4000-8000-000000000001"
TARGET_ID = "60000000-0000-4000-8000-000000000001"


def test_normalize_data_product_to_data_asset_relationship() -> None:
    result = normalize_governance_relationship(
        {"entityId": TARGET_ID, "relationshipType": "Related"},
        source_type="dataProduct",
        source_id=SOURCE_ID,
        target_category="DATAASSET",
    )
    assert isinstance(result, NormalizedGovernanceRelationship)
    doc = result.to_document()
    assert doc["sourceType"] == "dataProduct"
    assert doc["targetCategory"] == "DATAASSET"
    assert doc["targetId"] == TARGET_ID
