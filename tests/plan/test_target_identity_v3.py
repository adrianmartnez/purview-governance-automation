"""Tests for v3 Unified Catalog target context identity."""

from __future__ import annotations

from purview_governance.plan.identity import (
    TARGET_CONTEXT_IDENTITY_TYPE,
    TARGET_CONTEXT_IDENTITY_TYPE_V3,
    compute_domain_identity,
    compute_target_context_identity,
    compute_target_context_identity_v3,
)

ENDPOINT = "https://account.purview.azure.com"
TENANT_ID = "20000000-0000-4000-8000-000000000001"


def test_target_context_identity_v3_uses_identity_type() -> None:
    identity = compute_target_context_identity_v3(
        surface="unifiedCatalog",
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
    )
    expected = compute_domain_identity(
        {
            "identityType": TARGET_CONTEXT_IDENTITY_TYPE_V3,
            "surface": "unifiedCatalog",
            "tenantId": TENANT_ID,
            "endpoint": ENDPOINT,
        }
    )
    assert identity == expected
    assert identity.startswith("sha256:")


def test_target_context_identity_v3_differs_from_v1() -> None:
    v1 = compute_target_context_identity(ENDPOINT)
    v3 = compute_target_context_identity_v3(
        surface="unifiedCatalog",
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
    )
    assert v1 != v3


def test_v1_target_identity_still_uses_v1_identity_type() -> None:
    identity = compute_target_context_identity(ENDPOINT)
    expected = compute_domain_identity(
        {
            "identityType": TARGET_CONTEXT_IDENTITY_TYPE,
            "endpoint": ENDPOINT,
        }
    )
    assert identity == expected
