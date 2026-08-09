"""AzureStorage remote-state allowlists and field classification."""

from __future__ import annotations

SUPPORTED_KIND = "AzureStorage"

TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {"name", "kind", "properties", "creationType", "id", "scans"}
)

PROPERTIES_KNOWN: frozenset[str] = frozenset(
    {
        "endpoint",
        "collection",
        "createdAt",
        "lastModifiedAt",
        "dataSourceCollectionMovingState",
        "dataUseGovernance",
        "location",
        "resourceGroup",
        "resourceId",
        "resourceName",
        "subscriptionId",
    }
)

COLLECTION_KNOWN: frozenset[str] = frozenset({"referenceName", "type", "lastModifiedAt"})

CREATION_TYPES: frozenset[str] = frozenset({"Manual", "AutoNative", "AutoManaged"})

MOVING_STATES_TEXTUAL: frozenset[str] = frozenset({"Active", "Moving", "Failed"})

# Official Get example wire quirk only — never mapped to Active.
LEGACY_MOVING_RAW = "0"

DATA_USE_GOVERNANCE_VALUES: frozenset[str] = frozenset(
    {
        "Disabled",
        "DisabledByAnotherAccount",
        "Enabled",
        "EnabledAtAncestorScope",
    }
)

COLLECTION_TYPE_EXPECTED = "CollectionReference"

VOLATILE_PROPERTY_FIELDS: frozenset[str] = frozenset({"createdAt", "lastModifiedAt"})
VOLATILE_COLLECTION_FIELDS: frozenset[str] = frozenset({"lastModifiedAt"})
