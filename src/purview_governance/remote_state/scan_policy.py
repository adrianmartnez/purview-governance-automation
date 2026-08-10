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

# Configurable fields not in Supported Material. Absent/null => SAFE ABSENT;
# any explicit non-null value => recorded for later DIFF blocked.
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

SCAN_UNSUPPORTED_TOP_LEVEL_FIELDS: frozenset[str] = frozenset({"dataSourceIdentifier"})

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

SCANNING_RULE_KNOWN: frozenset[str] = frozenset({"fileExtensions"})
