"""Data Product enumerate allowlists and deferred-field policy (remote-state/v3)."""

from __future__ import annotations

from typing import Literal

DataProductStatus = Literal["DRAFT", "PUBLISHED", "EXPIRED"]
ProvisioningState = Literal["Unknown", "Succeeded", "SoftDeleted"]

DATA_PRODUCT_STATUSES: frozenset[str] = frozenset({"DRAFT", "PUBLISHED", "EXPIRED"})
PROVISIONING_STATES: frozenset[str] = frozenset({"Unknown", "Succeeded", "SoftDeleted"})

DATA_PRODUCT_TYPES: frozenset[str] = frozenset(
    {
        "Master",
        "Reference",
        "Analytical",
        "AI",
        "MasterDataAndReferenceData",
        "BusinessSystemOrApplication",
        "ModelTypes",
        "DashboardsOrReports",
        "Operational",
        "MLAITrainingDataSet",
        "MLAITestingDataSet",
        "TransactionalDataset",
        "AnalyticsModel",
        "SemanticModel",
    },
)

AUDIENCE_VALUES: frozenset[str] = frozenset(
    {
        "DataEngineer",
        "BIEngineer",
        "DataAnalyst",
        "DataScientist",
        "BusinessAnalyst",
        "SoftwareEngineer",
        "BusinessUser",
        "Executive",
    },
)

UPDATE_FREQUENCY_VALUES: frozenset[str] = frozenset(
    {
        "Hourly",
        "Daily",
        "Weekly",
        "Monthly",
        "Quarterly",
        "Yearly",
    },
)

DATA_PRODUCT_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "domain",
        "type",
        "description",
        "businessUse",
        "status",
        "contacts",
        "audience",
        "updateFrequency",
        "endorsed",
        "managedAttributes",
        "termsOfUse",
        "documentation",
        "sensitivityLabel",
        "activeSubscriberCount",
        "dataQualityScore",
        "additionalProperties",
        "systemData",
    },
)

DATA_PRODUCT_COMPARABLE_PROPERTIES: frozenset[str] = frozenset(
    {
        "name",
        "domain",
        "type",
        "description",
        "businessUse",
        "owners",
        "audience",
        "updateFrequency",
        "endorsed",
    },
)

DEFERRED_CONFIGURABLE_FIELDS: frozenset[str] = frozenset(
    {
        "managedAttributes",
        "termsOfUse",
        "documentation",
        "sensitivityLabel",
    },
)

DEFERRED_CONTACT_PATHS: tuple[str, ...] = (
    "/contacts/expert",
    "/contacts/databaseAdmin",
)

DEFERRED_FIELD_PATHS: tuple[str, ...] = (
    "/managedAttributes",
    "/termsOfUse",
    "/documentation",
    "/sensitivityLabel",
)

CONTACTS_MAP_KNOWN: frozenset[str] = frozenset({"owner", "expert", "databaseAdmin"})
CONTACT_ENTRY_KNOWN: frozenset[str] = frozenset({"id", "description"})
MANAGED_ATTRIBUTE_KNOWN: frozenset[str] = frozenset({"name", "value", "isRequired"})
EXTERNAL_LINK_KNOWN: frozenset[str] = frozenset({"url", "name", "dataAssetId"})
ADDITIONAL_PROPERTIES_KNOWN: frozenset[str] = frozenset({"assetCount"})
SYSTEM_DATA_KNOWN: frozenset[str] = frozenset(
    {
        "createdAt",
        "createdBy",
        "lastModifiedAt",
        "lastModifiedBy",
        "expiredAt",
        "expiredBy",
        "provisioningState",
    },
)

REASON_INVALID_SHAPE = "remote_state.invalid_shape"
REASON_UNKNOWN_FIELD = "remote_state.unknown_field"
REASON_DUPLICATE_OWNER_ID = "remote_state.duplicate_owner_id"
REASON_DUPLICATE_AUDIENCE = "remote_state.duplicate_audience"
REASON_UNSUPPORTED_TYPE = "remote_state.unsupported_data_product_type"
REASON_PROVISIONING_BLOCKED = "remote_state.provisioning_state_blocked"

CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN = "businessDomain"
CAPTURED_RESOURCE_TYPE_DATA_PRODUCT = "dataProduct"
