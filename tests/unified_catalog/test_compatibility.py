"""Unit tests for Unified Catalog compatibility metadata."""

from __future__ import annotations

import pytest

from purview_governance.unified_catalog import (
    UNIFIED_CATALOG_API_SURFACE,
    UNIFIED_CATALOG_API_VERSION,
    UNIFIED_CATALOG_RELEASE_STATUS,
    describe_compatibility,
    supported_api_versions,
    validate_unified_catalog_api_version,
)
from purview_governance.unified_catalog.errors import UnifiedCatalogCompatibilityError


def test_supported_api_versions_is_pinned_preview() -> None:
    versions = supported_api_versions()
    assert versions == frozenset({"2026-03-20-preview"})


def test_describe_compatibility_metadata() -> None:
    report = describe_compatibility()
    assert report.api_surface == UNIFIED_CATALOG_API_SURFACE == "unified-catalog"
    assert report.release_status == UNIFIED_CATALOG_RELEASE_STATUS == "public-preview"
    assert report.runtime_api_version == UNIFIED_CATALOG_API_VERSION
    assert report.supported_api_versions == frozenset({UNIFIED_CATALOG_API_VERSION})


def test_validate_unified_catalog_api_version_accepts_supported() -> None:
    validate_unified_catalog_api_version(UNIFIED_CATALOG_API_VERSION)


def test_validate_unified_catalog_api_version_rejects_unsupported() -> None:
    with pytest.raises(UnifiedCatalogCompatibilityError) as exc:
        validate_unified_catalog_api_version("2025-09-15-preview")
    assert exc.value.code == "unified_catalog.unsupported_api_version"
