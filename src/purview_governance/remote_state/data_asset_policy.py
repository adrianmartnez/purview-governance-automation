"""Data Asset enumerate allowlists and normalization policy (remote-state/v3 read model)."""

from __future__ import annotations

from typing import Literal

DataAssetType = Literal["General", "AzureSqlTable", "ADLSGen2Path"]
ProvisioningState = Literal["Unknown", "Succeeded", "SoftDeleted"]

DATA_ASSET_TYPES: frozenset[str] = frozenset({"General", "AzureSqlTable", "ADLSGen2Path"})
PROVISIONING_STATES: frozenset[str] = frozenset({"Unknown", "Succeeded", "SoftDeleted"})
TYPE_PROPERTIES_FORMAT: frozenset[str] = frozenset({"Table", "View"})

DATA_ASSET_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "type",
        "description",
        "openInUrl",
        "source",
        "contacts",
        "classifications",
        "schema",
        "typeProperties",
        "systemData",
    }
)

SOURCE_KNOWN: frozenset[str] = frozenset(
    {
        "type",
        "assetId",
        "assetType",
        "fqn",
        "accountName",
        "assetAttributes",
        "lastRefreshedAt",
        "lastRefreshedBy",
    }
)

CONTACTS_MAP_KNOWN: frozenset[str] = frozenset({"owner", "expert", "databaseAdmin"})
CONTACT_ENTRY_KNOWN: frozenset[str] = frozenset({"id", "description"})

SCHEMA_ENTRY_KNOWN: frozenset[str] = frozenset({"name", "description", "type", "classifications"})

AZURE_SQL_TABLE_TYPE_PROPERTIES_KNOWN: frozenset[str] = frozenset(
    {"format", "serverEndpoint", "databaseName", "schemaName", "tableName"}
)

ADLS_GEN2_PATH_TYPE_PROPERTIES_KNOWN: frozenset[str] = frozenset(
    {"serverEndpoint", "container", "folderPath", "fileName"}
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
REASON_DUPLICATE_OWNER_ID = "remote_state.duplicate_owner_id"
REASON_DUPLICATE_CLASSIFICATION = "remote_state.duplicate_classification"
REASON_PROVISIONING_BLOCKED = "remote_state.provisioning_state_blocked"
REASON_UNSUPPORTED_TYPE = "remote_state.unsupported_type"
