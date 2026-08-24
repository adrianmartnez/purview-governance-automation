"""Governance relationship enumerate allowlists and normalization policy."""

from __future__ import annotations

from typing import Literal

from purview_governance.remote_state.read_model_coverage_policy import (
    GOVERNANCE_RELATIONSHIP_SOURCE_TYPES,
    GOVERNANCE_RELATIONSHIP_TARGET_CATEGORIES,
    RELATIONSHIP_FAMILIES,
)

GovernanceRelationshipSourceType = Literal["dataProduct", "glossaryTerm"]
GovernanceRelationshipTargetCategory = Literal["DATAASSET", "DATACOLUMN"]
RelationshipFamily = Literal[
    "dataProductToDataAsset",
    "glossaryTermToDataAsset",
    "glossaryTermToDataColumn",
]

RELATIONSHIP_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "entityId",
        "entityType",
        "relationshipType",
        "targetId",
        "targetType",
        "description",
        "systemData",
    }
)

RELATIONSHIP_SYSTEM_DATA_KNOWN: frozenset[str] = frozenset(
    {
        "createdAt",
        "createdBy",
        "lastModifiedAt",
        "lastModifiedBy",
        "expiredAt",
        "expiredBy",
        "provisioningState",
    }
)

REASON_INVALID_SHAPE = "remote_state.invalid_shape"
REASON_UNKNOWN_FIELD = "remote_state.unknown_field"
REASON_UNSUPPORTED_RELATIONSHIP_TYPE = "remote_state.unsupported_relationship_type"
REASON_UNSUPPORTED_TARGET_CATEGORY = "remote_state.unsupported_target_category"
REASON_UNSUPPORTED_SOURCE_TYPE = "remote_state.unsupported_source_type"
REASON_UNSUPPORTED_FAMILY = "remote_state.unsupported_relationship_family"

APPROVED_RELATIONSHIP_TYPES: frozenset[str] = frozenset({"Related"})

__all__ = [
    "APPROVED_RELATIONSHIP_TYPES",
    "GOVERNANCE_RELATIONSHIP_SOURCE_TYPES",
    "GOVERNANCE_RELATIONSHIP_TARGET_CATEGORIES",
    "RELATIONSHIP_FAMILIES",
    "RELATIONSHIP_SYSTEM_DATA_KNOWN",
    "RELATIONSHIP_TOP_LEVEL_KNOWN",
    "REASON_INVALID_SHAPE",
    "REASON_UNKNOWN_FIELD",
    "REASON_UNSUPPORTED_FAMILY",
    "REASON_UNSUPPORTED_RELATIONSHIP_TYPE",
    "REASON_UNSUPPORTED_SOURCE_TYPE",
    "REASON_UNSUPPORTED_TARGET_CATEGORY",
    "GovernanceRelationshipSourceType",
    "GovernanceRelationshipTargetCategory",
    "RelationshipFamily",
]
