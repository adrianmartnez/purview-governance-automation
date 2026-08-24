"""Business Domain enumerate allowlists and deferred-field policy (remote-state/v3)."""

from __future__ import annotations

from typing import Literal

BusinessDomainStatus = Literal["DRAFT", "PUBLISHED", "EXPIRED"]
BusinessDomainType = Literal[
    "FunctionalUnit",
    "LineOfBusiness",
    "DataDomain",
    "Regulatory",
    "Project",
]

BUSINESS_DOMAIN_STATUSES: frozenset[str] = frozenset(
    {"DRAFT", "PUBLISHED", "EXPIRED"},
)
BUSINESS_DOMAIN_TYPES: frozenset[str] = frozenset(
    {
        "FunctionalUnit",
        "LineOfBusiness",
        "DataDomain",
        "Regulatory",
        "Project",
    },
)
PARENT_COLLECTION_TYPES: frozenset[str] = frozenset({"CollectionReference"})

BUSINESS_DOMAIN_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "description",
        "parentId",
        "status",
        "type",
        "isRestricted",
        "managedAttributes",
        "domains",
        "thumbnail",
        "systemData",
    },
)

BUSINESS_DOMAIN_COMPARABLE_PROPERTIES: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "parentId",
        "status",
        "type",
        "isRestricted",
    },
)

DEFERRED_CONFIGURABLE_FIELDS: frozenset[str] = frozenset(
    {"managedAttributes", "domains", "thumbnail"},
)

DEFERRED_FIELD_PATHS: tuple[str, ...] = (
    "/managedAttributes",
    "/domains",
    "/thumbnail",
)

MANAGED_ATTRIBUTE_KNOWN: frozenset[str] = frozenset({"name", "value", "isRequired"})
PLATFORM_DOMAIN_KNOWN: frozenset[str] = frozenset(
    {"name", "friendlyName", "relatedCollections"},
)
RELATED_COLLECTION_KNOWN: frozenset[str] = frozenset(
    {"name", "friendlyName", "parentCollection"},
)
PARENT_COLLECTION_KNOWN: frozenset[str] = frozenset({"refName", "type"})
THUMBNAIL_KNOWN: frozenset[str] = frozenset({"color"})

REASON_HIERARCHY_AMBIGUOUS = "remote_state.hierarchy_ambiguous"
