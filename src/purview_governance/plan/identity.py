"""Domain-separated SHA-256 identities for purview-governance-plan/v1."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from purview_governance.remote_state.canonical import dumps_canonical

PLAN_API_VERSION = "purview-governance-plan/v1"
PLAN_API_VERSION_V2 = "purview-governance-plan/v2"
CONFIGURATION_API_VERSION = "purview-governance-config/v1"
CONFIGURATION_API_VERSION_V2 = "purview-governance-config/v2"

HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

TARGET_CONTEXT_IDENTITY_TYPE = "purview-target-context/v1"
DESIRED_STATE_IDENTITY_TYPE = "purview-desired-state/v1"
MATERIAL_CONFIGURATION_IDENTITY_TYPE = "purview-material-configuration/v1"


def is_sha256_identity(value: object) -> bool:
    return isinstance(value, str) and HASH_PATTERN.fullmatch(value) is not None


def compute_domain_identity(identity_document: dict[str, Any]) -> str:
    """Return ``sha256:<hex>`` for a domain-discriminated identity document."""
    canonical_bytes = dumps_canonical(identity_document).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest}"


def compute_target_context_identity(endpoint: str) -> str:
    return compute_domain_identity(
        {
            "identityType": TARGET_CONTEXT_IDENTITY_TYPE,
            "endpoint": endpoint,
        }
    )


def compute_desired_state_identity(desired_state_document: dict[str, Any]) -> str:
    return compute_domain_identity(
        {
            "identityType": DESIRED_STATE_IDENTITY_TYPE,
            "state": desired_state_document,
        }
    )


def compute_material_configuration_identity(
    *,
    target_context_identity: str,
    desired_state_identity: str,
    configuration_api_version: str = CONFIGURATION_API_VERSION,
) -> str:
    return compute_domain_identity(
        {
            "identityType": MATERIAL_CONFIGURATION_IDENTITY_TYPE,
            "configurationApiVersion": configuration_api_version,
            "desiredStateIdentity": desired_state_identity,
            "targetContextIdentity": target_context_identity,
        }
    )


def compute_plan_identity(plan_document_without_identity: dict[str, Any]) -> str:
    """Hash plan document without ``planIdentity`` (apiVersion discriminates domain)."""
    if "planIdentity" in plan_document_without_identity:
        msg = "plan identity document must not contain planIdentity"
        raise ValueError(msg)
    return compute_domain_identity(plan_document_without_identity)
