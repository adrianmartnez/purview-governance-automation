"""Domain-separated identities for purview-execution-result/v1."""

from __future__ import annotations

from typing import Any

from purview_governance.plan.identity import compute_domain_identity, is_sha256_identity

RESULT_API_VERSION = "purview-execution-result/v1"

__all__ = [
    "RESULT_API_VERSION",
    "compute_result_identity",
    "is_sha256_identity",
]


def compute_result_identity(result_document_without_identity: dict[str, Any]) -> str:
    """Hash result document without ``resultIdentity`` (apiVersion discriminates domain)."""
    if "resultIdentity" in result_document_without_identity:
        msg = "result identity document must not contain resultIdentity"
        raise ValueError(msg)
    return compute_domain_identity(result_document_without_identity)
