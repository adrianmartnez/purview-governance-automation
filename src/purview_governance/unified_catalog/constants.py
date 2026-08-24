"""Unified Catalog Public Preview constants (API version, host, timeouts)."""

from __future__ import annotations

import httpx

UNIFIED_CATALOG_API_VERSION = "2026-03-20-preview"
UNIFIED_CATALOG_API_SURFACE = "unified-catalog"
UNIFIED_CATALOG_RELEASE_STATUS = "public-preview"

# Documented production service host (Microsoft Learn, 2026-03-20-preview).
UNIFIED_CATALOG_PRODUCTION_HOST = "api.purview-service.microsoft.com"
UNIFIED_CATALOG_PRODUCTION_ENDPOINT = f"https://{UNIFIED_CATALOG_PRODUCTION_HOST}"

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0
WRITE_TIMEOUT_SECONDS = 30.0
POOL_TIMEOUT_SECONDS = 5.0

MAX_LIST_PAGES = 50

DEFAULT_TIMEOUT = httpx.Timeout(
    CONNECT_TIMEOUT_SECONDS,
    connect=CONNECT_TIMEOUT_SECONDS,
    read=READ_TIMEOUT_SECONDS,
    write=WRITE_TIMEOUT_SECONDS,
    pool=POOL_TIMEOUT_SECONDS,
)

BUSINESS_DOMAINS_PATH = "/datagovernance/catalog/businessdomains"
DATA_PRODUCTS_PATH = "/datagovernance/catalog/dataProducts"
GLOSSARY_TERMS_PATH = "/datagovernance/catalog/terms"
DATA_ASSETS_PATH = "/datagovernance/catalog/dataAssets"
DATA_COLUMNS_QUERY_PATH = "/datagovernance/catalog/dataColumns/query"

DATA_COLUMN_QUERY_PAGE_SIZE = 100
