"""Microsoft Purview Unified Catalog Public Preview client foundation."""

from purview_governance.unified_catalog.client import (
    BusinessDomainListResult,
    PurviewUnifiedCatalogClient,
)
from purview_governance.unified_catalog.compatibility import (
    CompatibilityReport,
    describe_compatibility,
    supported_api_versions,
    validate_unified_catalog_api_version,
)
from purview_governance.unified_catalog.constants import (
    UNIFIED_CATALOG_API_SURFACE,
    UNIFIED_CATALOG_API_VERSION,
    UNIFIED_CATALOG_PRODUCTION_ENDPOINT,
    UNIFIED_CATALOG_PRODUCTION_HOST,
    UNIFIED_CATALOG_RELEASE_STATUS,
)
from purview_governance.unified_catalog.endpoint import normalize_unified_catalog_endpoint
from purview_governance.unified_catalog.errors import (
    UnifiedCatalogClientError,
    UnifiedCatalogCompatibilityError,
    UnifiedCatalogHttpError,
    UnifiedCatalogPaginationError,
    UnifiedCatalogRequestBuildError,
    UnifiedCatalogRequestError,
    UnifiedCatalogResponseError,
    UnifiedCatalogTimeoutError,
)

__all__ = [
    "UNIFIED_CATALOG_API_SURFACE",
    "UNIFIED_CATALOG_API_VERSION",
    "UNIFIED_CATALOG_PRODUCTION_ENDPOINT",
    "UNIFIED_CATALOG_PRODUCTION_HOST",
    "UNIFIED_CATALOG_RELEASE_STATUS",
    "BusinessDomainListResult",
    "CompatibilityReport",
    "PurviewUnifiedCatalogClient",
    "UnifiedCatalogClientError",
    "UnifiedCatalogCompatibilityError",
    "UnifiedCatalogHttpError",
    "UnifiedCatalogPaginationError",
    "UnifiedCatalogRequestBuildError",
    "UnifiedCatalogRequestError",
    "UnifiedCatalogResponseError",
    "UnifiedCatalogTimeoutError",
    "describe_compatibility",
    "normalize_unified_catalog_endpoint",
    "supported_api_versions",
    "validate_unified_catalog_api_version",
]
