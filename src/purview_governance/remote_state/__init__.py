"""Read-only Purview remote-state (purview-remote-state/v1, /v2, and /v3)."""

from __future__ import annotations

from purview_governance.remote_state.canonical import dumps_canonical
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.models import (
    REMOTE_STATE_API_VERSION,
    REMOTE_STATE_API_VERSION_V2,
    NormalizedClassificationRule,
    NormalizedDataSource,
    NormalizedScan,
    NormalizedScanRuleSet,
    ObservedProperties,
    RemoteState,
    RemoteStateV2,
    ScanObservedProperties,
    UninterpretedClassificationRule,
    UninterpretedDataSource,
    UninterpretedScan,
    UninterpretedScanRuleSet,
    UnknownLegacyMovingState,
    UnsupportedConfigurableField,
    build_remote_state,
    build_remote_state_v2,
)
from purview_governance.remote_state.models_v3 import (
    REMOTE_STATE_API_VERSION_V3,
    NormalizedBusinessDomain,
    RemoteStateV3,
    RemoteTargetContextV3,
    UninterpretedBusinessDomain,
    build_remote_state_v3,
    remote_observed_count_v3,
)
from purview_governance.remote_state.schema import (
    load_remote_state_v1_schema,
    load_remote_state_v2_schema,
    load_remote_state_v3_schema,
)
from purview_governance.remote_state.service import (
    DataSourceReadClient,
    ScanningReadClient,
    UnifiedCatalogReadClient,
    capture_remote_state,
    capture_remote_state_v2,
    capture_unified_catalog_remote_state_v3,
)

# Lazy: loader_v3 imports plan.identity; avoid circular import via package __init__.
_LAZY_EXPORTS = {
    "load_remote_state_v3_file": "purview_governance.remote_state.loader_v3",
    "load_remote_state_v3_text": "purview_governance.remote_state.loader_v3",
}


def __getattr__(name: str) -> object:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(_LAZY_EXPORTS[name])
    return getattr(module, name)


__all__ = [
    "REMOTE_STATE_API_VERSION",
    "REMOTE_STATE_API_VERSION_V2",
    "REMOTE_STATE_API_VERSION_V3",
    "DataSourceReadClient",
    "NormalizedBusinessDomain",
    "NormalizedClassificationRule",
    "NormalizedDataSource",
    "NormalizedScan",
    "NormalizedScanRuleSet",
    "ObservedProperties",
    "RemoteState",
    "RemoteStateError",
    "RemoteStateV2",
    "RemoteStateV3",
    "RemoteTargetContextV3",
    "ScanObservedProperties",
    "ScanningReadClient",
    "UnifiedCatalogReadClient",
    "UninterpretedBusinessDomain",
    "UninterpretedClassificationRule",
    "UninterpretedDataSource",
    "UninterpretedScan",
    "UninterpretedScanRuleSet",
    "UnknownLegacyMovingState",
    "UnsupportedConfigurableField",
    "build_remote_state",
    "build_remote_state_v2",
    "build_remote_state_v3",
    "capture_remote_state",
    "capture_remote_state_v2",
    "capture_unified_catalog_remote_state_v3",
    "dumps_canonical",
    "load_remote_state_v1_schema",
    "load_remote_state_v2_schema",
    "load_remote_state_v3_file",
    "load_remote_state_v3_schema",
    "load_remote_state_v3_text",
    "remote_observed_count_v3",
]
