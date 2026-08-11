"""Microsoft Purview Scanning Data Plane client foundation."""

from purview_governance.scanning.client import (
    ClassificationRuleListResult,
    DataSourceListResult,
    PurviewScanningClient,
    ScanListResult,
    ScanRuleSetListResult,
)
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
    "ClassificationRuleListResult",
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
    "ScanListResult",
    "ScanRuleSetListResult",
]
