"""Data Column enumerate allowlists and normalization policy (remote-state/v3 read model)."""

from __future__ import annotations

from typing import Literal

DataColumnType = Literal["General", "AzureSqlColumn", "ADLSGen2Path"]

DATA_COLUMN_TYPES: frozenset[str] = frozenset({"General", "AzureSqlColumn", "ADLSGen2Path"})
PROVISIONING_STATES: frozenset[str] = frozenset({"Unknown", "Succeeded", "SoftDeleted"})

DATA_COLUMN_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "type",
        "description",
        "source",
        "columnDetails",
        "assetDetails",
        "systemData",
    }
)

SOURCE_KNOWN: frozenset[str] = frozenset(
    {
        "type",
        "assetId",
        "assetType",
        "columnId",
        "fqn",
        "accountName",
        "assetAttributes",
        "lastRefreshedAt",
        "lastRefreshedBy",
    }
)

COLUMN_DETAILS_KNOWN: frozenset[str] = frozenset(
    {
        "dataType",
        "isNullable",
        "ordinalPosition",
        "maxLength",
        "precision",
        "scale",
    }
)

ASSET_DETAILS_KNOWN: frozenset[str] = frozenset(
    {"assetId", "assetType", "fqn", "accountName", "assetAttributes", "name"}
)

SYSTEM_DATA_KNOWN: frozenset[str] = frozenset(
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
REASON_PROVISIONING_BLOCKED = "remote_state.provisioning_state_blocked"
REASON_UNSUPPORTED_TYPE = "remote_state.unsupported_type"
