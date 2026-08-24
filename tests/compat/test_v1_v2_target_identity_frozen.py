"""Frozen v1/v2 target context identity regression tests."""

from __future__ import annotations

from purview_governance.plan.identity import (
    TARGET_CONTEXT_IDENTITY_TYPE,
    compute_domain_identity,
    compute_target_context_identity,
)

ENDPOINT = "https://account.purview.azure.com"
FROZEN_V1_IDENTITY = compute_domain_identity(
    {
        "identityType": TARGET_CONTEXT_IDENTITY_TYPE,
        "endpoint": ENDPOINT,
    }
)


def test_v1_target_context_identity_frozen() -> None:
    assert compute_target_context_identity(ENDPOINT) == FROZEN_V1_IDENTITY


def test_v1_target_context_identity_stable_across_calls() -> None:
    first = compute_target_context_identity(ENDPOINT)
    second = compute_target_context_identity(ENDPOINT)
    assert first == second == FROZEN_V1_IDENTITY
