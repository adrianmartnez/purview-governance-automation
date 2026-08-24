"""Unified Catalog API surface compatibility metadata and validation."""

from __future__ import annotations

from dataclasses import dataclass

from purview_governance.unified_catalog.constants import (
    UNIFIED_CATALOG_API_SURFACE,
    UNIFIED_CATALOG_API_VERSION,
    UNIFIED_CATALOG_RELEASE_STATUS,
)
from purview_governance.unified_catalog.errors import UnifiedCatalogCompatibilityError

_SUPPORTED_VERSIONS = frozenset({UNIFIED_CATALOG_API_VERSION})


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    """Stable compatibility metadata for the Unified Catalog adapter."""

    api_surface: str
    release_status: str
    supported_api_versions: frozenset[str]
    runtime_api_version: str


def supported_api_versions() -> frozenset[str]:
    """Return API versions supported by this package release."""
    return _SUPPORTED_VERSIONS


def describe_compatibility() -> CompatibilityReport:
    """Describe the supported Unified Catalog Public Preview surface."""
    return CompatibilityReport(
        api_surface=UNIFIED_CATALOG_API_SURFACE,
        release_status=UNIFIED_CATALOG_RELEASE_STATUS,
        supported_api_versions=_SUPPORTED_VERSIONS,
        runtime_api_version=UNIFIED_CATALOG_API_VERSION,
    )


def validate_unified_catalog_api_version(version: str) -> None:
    """Validate an API version for future config/document consumers.

    The production client runtime is pinned to ``UNIFIED_CATALOG_API_VERSION``.
    This helper does not enable runtime version selection in PR1.
    """
    if version not in _SUPPORTED_VERSIONS:
        raise UnifiedCatalogCompatibilityError(
            "unified_catalog.unsupported_api_version",
            "Unified Catalog API version is not supported by this package release",
        )
