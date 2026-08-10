"""AzureStorageMsi Scan and Custom AzureStorage Scan Rule Set allowlists."""

from __future__ import annotations

SUPPORTED_SCAN_KIND = "AzureStorageMsi"
SUPPORTED_SCAN_RULESET_KIND = "AzureStorage"
SUPPORTED_SCAN_RULESET_TYPE = "Custom"

SCAN_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "name",
        "kind",
        "properties",
        "creationType",
        "id",
        "scanId",
        "lastRunResult",
        "dataSourceName",
        "dataSourceIdentifier",
    }
)

SCAN_PROPERTIES_KNOWN: frozenset[str] = frozenset(
    {
        "scanRulesetName",
        "scanRulesetType",
        "collection",
        "connectedVia",
        "domain",
        "isLiveViewEnabled",
        "isPresetScan",
        "logLevel",
        "parallelScanCount",
        "workers",
        "businessRuleSetName",
        "createdAt",
        "lastModifiedAt",
    }
)

# Configurable fields not in Supported Material.
# Per-field null policy (absent vs null vs explicit):
#
# | Field                 | absent | null                         | explicit non-null              |
# |-----------------------|--------|------------------------------|--------------------------------|
# | connectedVia          | safe   | safe (Create/Get samples)    | object => unsupported+identity |
# | domain                | safe   | safe (optional string)       | string (incl "") => unsupported|
# | isLiveViewEnabled     | safe   | FAIL malformed (boolean)     | bool => unsupported            |
# | isPresetScan          | safe   | FAIL malformed               | bool => unsupported            |
# | logLevel              | safe   | safe (optional string)       | string => unsupported          |
# | parallelScanCount     | safe   | FAIL malformed (int)         | int => unsupported             |
# | workers               | safe   | FAIL malformed               | int => unsupported             |
# | businessRuleSetName   | safe   | safe                         | string => unsupported          |
# | dataSourceIdentifier  | safe   | safe                         | object => unsupported          |
#
# Malformed wrong types (e.g. string for boolean) => fail-closed.
SCAN_UNSUPPORTED_PROPERTY_FIELDS: frozenset[str] = frozenset(
    {
        "connectedVia",
        "domain",
        "isLiveViewEnabled",
        "isPresetScan",
        "logLevel",
        "parallelScanCount",
        "workers",
        "businessRuleSetName",
    }
)

# Null on the wire is SAFE ABSENT (official samples use null for optional unset).
SCAN_UNSUPPORTED_NULL_SAFE_PROPERTY_FIELDS: frozenset[str] = frozenset(
    {
        "connectedVia",
        "domain",
        "logLevel",
        "businessRuleSetName",
    }
)

# Null is malformed: typed booleans/ints must not appear as JSON null.
SCAN_UNSUPPORTED_NULL_FAIL_PROPERTY_FIELDS: frozenset[str] = frozenset(
    {
        "isLiveViewEnabled",
        "isPresetScan",
        "parallelScanCount",
        "workers",
    }
)

SCAN_UNSUPPORTED_TOP_LEVEL_FIELDS: frozenset[str] = frozenset({"dataSourceIdentifier"})
SCAN_UNSUPPORTED_NULL_SAFE_TOP_LEVEL_FIELDS: frozenset[str] = frozenset({"dataSourceIdentifier"})

SCAN_VOLATILE_PROPERTY_FIELDS: frozenset[str] = frozenset({"createdAt", "lastModifiedAt"})

SCAN_RULESET_TYPES: frozenset[str] = frozenset({"System", "Custom"})

SCAN_RULESET_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "name",
        "kind",
        "properties",
        "scanRulesetType",
        "id",
        "status",
        "version",
    }
)

SCAN_RULESET_PROPERTIES_KNOWN: frozenset[str] = frozenset(
    {
        "scanningRule",
        "excludedSystemClassifications",
        "includedCustomClassificationRuleNames",
        "description",
        "createdAt",
        "lastModifiedAt",
    }
)

SCAN_RULESET_VOLATILE_PROPERTY_FIELDS: frozenset[str] = frozenset({"createdAt", "lastModifiedAt"})

# Official ScanningRule includes customFileExtensions alongside fileExtensions.
# customFileExtensions: absent => OK; null => SAFE ABSENT; explicit (incl []) => unsupported.
SCANNING_RULE_KNOWN: frozenset[str] = frozenset({"fileExtensions", "customFileExtensions"})
