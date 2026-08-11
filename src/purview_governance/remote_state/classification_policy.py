"""Custom Classification Rule allowlists and materiality constants."""

from __future__ import annotations

SUPPORTED_CLASSIFICATION_RULE_KIND = "Custom"
SYSTEM_CLASSIFICATION_RULE_KIND = "System"

CLASSIFICATION_ACTIONS: frozenset[str] = frozenset({"Keep", "Delete"})
CLASSIFICATION_RULE_STATUSES: frozenset[str] = frozenset({"Enabled", "Disabled"})

INT32_MIN = -2147483648
INT32_MAX = 2147483647

CLASSIFICATION_RULE_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "name",
        "kind",
        "properties",
        "id",
    }
)

CLASSIFICATION_RULE_PROPERTIES_KNOWN: frozenset[str] = frozenset(
    {
        "classificationName",
        "columnPatterns",
        "dataPatterns",
        "description",
        "minimumPercentageMatch",
        "ruleStatus",
        "classificationAction",
        "version",
        "createdAt",
        "lastModifiedAt",
    }
)

# PUT Create-or-Replace material fields (desired-comparable).
CLASSIFICATION_RULE_MATERIAL_PROPERTY_FIELDS: frozenset[str] = frozenset(
    {
        "classificationName",
        "columnPatterns",
        "dataPatterns",
        "description",
        "minimumPercentageMatch",
        "ruleStatus",
    }
)

# Separately managed via Tag Classification Version (not desired PUT material).
CLASSIFICATION_RULE_SEPARATELY_MANAGED_FIELDS: frozenset[str] = frozenset(
    {
        "classificationAction",
        "version",
    }
)

CLASSIFICATION_RULE_VOLATILE_PROPERTY_FIELDS: frozenset[str] = frozenset(
    {
        "createdAt",
        "lastModifiedAt",
    }
)
