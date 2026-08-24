"""Glossary Term enumerate allowlists and deferred-field policy (remote-state/v3)."""

from __future__ import annotations

from typing import Literal

GlossaryTermStatus = Literal["DRAFT", "PUBLISHED", "EXPIRED"]
ProvisioningState = Literal["Unknown", "Succeeded", "SoftDeleted"]

GLOSSARY_TERM_STATUSES: frozenset[str] = frozenset({"DRAFT", "PUBLISHED", "EXPIRED"})
PROVISIONING_STATES: frozenset[str] = frozenset({"Unknown", "Succeeded", "SoftDeleted"})

GLOSSARY_TERM_TOP_LEVEL_KNOWN: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "domain",
        "description",
        "status",
        "contacts",
        "parentId",
        "acronyms",
        "resources",
        "managedAttributes",
        "isLeaf",
        "systemData",
    }
)

GLOSSARY_TERM_COMPARABLE_PROPERTIES: frozenset[str] = frozenset(
    {
        "name",
        "domain",
        "description",
        "owners",
        "parentId",
        "acronyms",
    }
)

DEFERRED_CONFIGURABLE_FIELDS: frozenset[str] = frozenset(
    {
        "managedAttributes",
        "resources",
    }
)

DEFERRED_CONTACT_PATHS: tuple[str, ...] = (
    "/contacts/expert",
    "/contacts/databaseAdmin",
)

CONTACTS_MAP_KNOWN: frozenset[str] = frozenset({"owner", "expert", "databaseAdmin"})
CONTACT_ENTRY_KNOWN: frozenset[str] = frozenset({"id", "description"})
MANAGED_ATTRIBUTE_KNOWN: frozenset[str] = frozenset({"name", "value", "isRequired"})
TERM_RESOURCE_KNOWN: frozenset[str] = frozenset({"name", "url"})
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
REASON_DUPLICATE_ACRONYM = "remote_state.duplicate_acronym"
REASON_PROVISIONING_BLOCKED = "remote_state.provisioning_state_blocked"
REASON_INVALID_PARENT_ID = "remote_state.invalid_parent_id"
REASON_INVALID_ACRONYMS = "remote_state.invalid_acronyms"

CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN = "businessDomain"
CAPTURED_RESOURCE_TYPE_DATA_PRODUCT = "dataProduct"
CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM = "glossaryTerm"

VALID_CAPTURE_MARKERS: frozenset[tuple[str, ...]] = frozenset(
    {
        (CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN, CAPTURED_RESOURCE_TYPE_DATA_PRODUCT),
        (CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN, CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM),
        (
            CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN,
            CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
            CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM,
        ),
    }
)
