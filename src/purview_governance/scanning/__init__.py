"""Microsoft Purview Scanning Data Plane client foundation."""

from purview_governance.scanning.client import DataSourceListResult, PurviewScanningClient
from purview_governance.scanning.constants import SCANNING_API_VERSION
from purview_governance.scanning.errors import (
    PurviewClientError,
    PurviewDataSourceNameError,
    PurviewHttpError,
    PurviewPaginationError,
    PurviewRequestBuildError,
    PurviewRequestError,
    PurviewResponseError,
    PurviewTimeoutError,
)

__all__ = [
    "SCANNING_API_VERSION",
    "DataSourceListResult",
    "PurviewClientError",
    "PurviewDataSourceNameError",
    "PurviewHttpError",
    "PurviewPaginationError",
    "PurviewRequestBuildError",
    "PurviewRequestError",
    "PurviewResponseError",
    "PurviewScanningClient",
    "PurviewTimeoutError",
]
