"""Strict loader for purview-remote-state/v3 artifacts (reject non-canonical input)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.canonical import compute_material_state_identity
from purview_governance.remote_state.data_product_policy import (
    CAPTURED_RESOURCE_TYPE_DATA_PRODUCT,
)
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.glossary_term_policy import (
    CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN,
    CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM,
    VALID_CAPTURE_MARKERS,
)
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    REMOTE_STATE_API_VERSION_V3,
    NormalizedBusinessDomain,
    NormalizedDataAsset,
    NormalizedDataColumn,
    NormalizedDataProduct,
    NormalizedGlossaryTerm,
    NormalizedGovernanceRelationship,
    ReadModelCoverageV3,
    RemoteStateV3,
    RemoteTargetContextV3,
    UninterpretedBusinessDomain,
    UninterpretedDataAsset,
    UninterpretedDataColumn,
    UninterpretedDataProduct,
    UninterpretedGlossaryTerm,
    UninterpretedGovernanceRelationship,
    build_remote_state_v3,
)
from purview_governance.remote_state.read_model_coverage_policy import (
    READ_MODEL_COVERAGE_DATA_ASSETS,
    READ_MODEL_COVERAGE_DATA_COLUMNS,
    READ_MODEL_COVERAGE_GOVERNANCE_RELATIONSHIPS,
    RELATIONSHIP_FAMILY_DATA_PRODUCT_TO_DATA_ASSET,
    RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_ASSET,
    RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_COLUMN,
)
from purview_governance.remote_state.schema import load_remote_state_v3_schema

_KNOWN_RELATIONSHIP_KEYS = frozenset(
    {
        "type",
        "sourceType",
        "sourceId",
        "targetCategory",
        "targetId",
        "relationshipType",
    }
)
_KNOWN_DATA_ASSET_KEYS = frozenset({"type", "id", "safetyProperties"})
_KNOWN_DATA_COLUMN_KEYS = frozenset({"type", "id"})


class _DuplicateKeyError(ValueError):
    def __init__(self, key: object) -> None:
        self.key = key
        super().__init__(f"duplicate key {key!r}")


def _object_pairs_hook(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _fail(code: str, message: str, *, path: str = "") -> None:
    raise RemoteStateError(code, message, path=path)


def _mapping(value: object, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("remote_state.invalid_syntax", "expected a JSON object", path=path)
    return value  # type: ignore[return-value]


def _list(value: object, *, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("remote_state.invalid_schema", "expected a JSON array", path=path)
    return value


def _str(value: object, *, path: str) -> str:
    if not isinstance(value, str) or value == "":
        _fail("remote_state.invalid_schema", "expected a non-empty string", path=path)
    return value


def _optional_str(value: object, *, path: str) -> str | None:
    if value is None:
        return None
    return _str(value, path=path)


def _unsupported_fields(raw: object, *, path: str) -> tuple[UnsupportedConfigurableField, ...]:
    if raw is None:
        return ()
    items = _list(raw, path=path)
    parsed: list[UnsupportedConfigurableField] = []
    for index, item in enumerate(items):
        item_path = f"{path}/{index}"
        mapping = _mapping(item, path=item_path)
        parsed.append(
            UnsupportedConfigurableField(
                path=_str(mapping.get("path"), path=f"{item_path}/path"),
                value_identity=_str(
                    mapping.get("valueIdentity"), path=f"{item_path}/valueIdentity"
                ),
            )
        )
    return tuple(parsed)


def _normalized_business_domain(raw: object, *, path: str) -> NormalizedBusinessDomain:
    mapping = _mapping(raw, path=path)
    properties = mapping.get("properties")
    if not isinstance(properties, dict):
        _fail(
            "remote_state.invalid_schema",
            "properties must be an object",
            path=f"{path}/properties",
        )
    return NormalizedBusinessDomain(
        id=_str(mapping.get("id"), path=f"{path}/id"),
        properties=dict(properties),
        unsupported_configurable_fields=_unsupported_fields(
            mapping.get("unsupportedConfigurableFields"),
            path=f"{path}/unsupportedConfigurableFields",
        ),
    )


def _uninterpreted_business_domain(raw: object, *, path: str) -> UninterpretedBusinessDomain:
    mapping = _mapping(raw, path=path)
    return UninterpretedBusinessDomain(
        reason_code=_str(mapping.get("reasonCode"), path=f"{path}/reasonCode"),
        id=_optional_str(mapping.get("id"), path=f"{path}/id"),
    )


def _normalized_data_product(raw: object, *, path: str) -> NormalizedDataProduct:
    mapping = _mapping(raw, path=path)
    properties = mapping.get("properties")
    safety = mapping.get("safetyProperties")
    if not isinstance(properties, dict):
        _fail(
            "remote_state.invalid_schema",
            "properties must be an object",
            path=f"{path}/properties",
        )
    if not isinstance(safety, dict):
        _fail(
            "remote_state.invalid_schema",
            "safetyProperties must be an object",
            path=f"{path}/safetyProperties",
        )
    return NormalizedDataProduct(
        id=_str(mapping.get("id"), path=f"{path}/id"),
        properties=dict(properties),
        safety_properties=dict(safety),
        unsupported_configurable_fields=_unsupported_fields(
            mapping.get("unsupportedConfigurableFields"),
            path=f"{path}/unsupportedConfigurableFields",
        ),
    )


def _uninterpreted_data_product(raw: object, *, path: str) -> UninterpretedDataProduct:
    mapping = _mapping(raw, path=path)
    return UninterpretedDataProduct(
        reason_code=_str(mapping.get("reasonCode"), path=f"{path}/reasonCode"),
        id=_optional_str(mapping.get("id"), path=f"{path}/id"),
    )


def _normalized_glossary_term(raw: object, *, path: str) -> NormalizedGlossaryTerm:
    mapping = _mapping(raw, path=path)
    properties = mapping.get("properties")
    safety = mapping.get("safetyProperties")
    if not isinstance(properties, dict):
        _fail(
            "remote_state.invalid_schema",
            "properties must be an object",
            path=f"{path}/properties",
        )
    if not isinstance(safety, dict):
        _fail(
            "remote_state.invalid_schema",
            "safetyProperties must be an object",
            path=f"{path}/safetyProperties",
        )
    return NormalizedGlossaryTerm(
        id=_str(mapping.get("id"), path=f"{path}/id"),
        properties=dict(properties),
        safety_properties=dict(safety),
        unsupported_configurable_fields=_unsupported_fields(
            mapping.get("unsupportedConfigurableFields"),
            path=f"{path}/unsupportedConfigurableFields",
        ),
    )


def _uninterpreted_glossary_term(raw: object, *, path: str) -> UninterpretedGlossaryTerm:
    mapping = _mapping(raw, path=path)
    return UninterpretedGlossaryTerm(
        reason_code=_str(mapping.get("reasonCode"), path=f"{path}/reasonCode"),
        id=_optional_str(mapping.get("id"), path=f"{path}/id"),
    )


def _normalized_data_asset(raw: object, *, path: str) -> NormalizedDataAsset:
    mapping = _mapping(raw, path=path)
    safety_raw = mapping.get("safetyProperties")
    safety: dict[str, Any] = {}
    if safety_raw is not None:
        if not isinstance(safety_raw, dict):
            _fail(
                "remote_state.invalid_schema",
                "safetyProperties must be an object",
                path=f"{path}/safetyProperties",
            )
        safety = dict(safety_raw)
    fields = {key: value for key, value in mapping.items() if key not in _KNOWN_DATA_ASSET_KEYS}
    return NormalizedDataAsset(
        id=_str(mapping.get("id"), path=f"{path}/id"),
        fields=fields,
        safety_properties=safety,
    )


def _uninterpreted_data_asset(raw: object, *, path: str) -> UninterpretedDataAsset:
    mapping = _mapping(raw, path=path)
    return UninterpretedDataAsset(
        reason_code=_str(mapping.get("reasonCode"), path=f"{path}/reasonCode"),
        id=_optional_str(mapping.get("id"), path=f"{path}/id"),
    )


def _normalized_data_column(raw: object, *, path: str) -> NormalizedDataColumn:
    mapping = _mapping(raw, path=path)
    fields = {key: value for key, value in mapping.items() if key not in _KNOWN_DATA_COLUMN_KEYS}
    return NormalizedDataColumn(
        id=_str(mapping.get("id"), path=f"{path}/id"),
        fields=fields,
    )


def _uninterpreted_data_column(raw: object, *, path: str) -> UninterpretedDataColumn:
    mapping = _mapping(raw, path=path)
    return UninterpretedDataColumn(
        reason_code=_str(mapping.get("reasonCode"), path=f"{path}/reasonCode"),
        id=_optional_str(mapping.get("id"), path=f"{path}/id"),
    )


def _normalized_relationship(raw: object, *, path: str) -> NormalizedGovernanceRelationship:
    mapping = _mapping(raw, path=path)
    fields = {key: value for key, value in mapping.items() if key not in _KNOWN_RELATIONSHIP_KEYS}
    return NormalizedGovernanceRelationship(
        source_type=_str(mapping.get("sourceType"), path=f"{path}/sourceType"),
        source_id=_str(mapping.get("sourceId"), path=f"{path}/sourceId"),
        target_category=_str(mapping.get("targetCategory"), path=f"{path}/targetCategory"),
        target_id=_str(mapping.get("targetId"), path=f"{path}/targetId"),
        relationship_type=_str(mapping.get("relationshipType"), path=f"{path}/relationshipType"),
        fields=fields,
    )


def _uninterpreted_relationship(raw: object, *, path: str) -> UninterpretedGovernanceRelationship:
    mapping = _mapping(raw, path=path)
    return UninterpretedGovernanceRelationship(
        reason_code=_str(mapping.get("reasonCode"), path=f"{path}/reasonCode"),
        source_type=_str(mapping.get("sourceType"), path=f"{path}/sourceType"),
        source_id=_str(mapping.get("sourceId"), path=f"{path}/sourceId"),
        target_category=_str(mapping.get("targetCategory"), path=f"{path}/targetCategory"),
        target_id=_optional_str(mapping.get("targetId"), path=f"{path}/targetId"),
        relationship_type=_optional_str(
            mapping.get("relationshipType"), path=f"{path}/relationshipType"
        ),
    )


def _read_model_coverage(raw: object, *, path: str) -> ReadModelCoverageV3:
    mapping = _mapping(raw, path=path)
    if not mapping:
        _fail(
            "remote_state.noncanonical_artifact",
            "readModelCoverage must not be empty when present",
            path=path,
        )
    for key, value in mapping.items():
        if key == READ_MODEL_COVERAGE_GOVERNANCE_RELATIONSHIPS:
            if not isinstance(value, dict) or not value:
                _fail(
                    "remote_state.noncanonical_artifact",
                    "governanceRelationships coverage must be a non-empty object",
                    path=f"{path}/{key}",
                )
            for rel_key, rel_value in value.items():
                if rel_value is not True:
                    _fail(
                        "remote_state.noncanonical_artifact",
                        "relationship coverage markers must be true when present",
                        path=f"{path}/{key}/{rel_key}",
                    )
            continue
        if value is False:
            _fail(
                "remote_state.noncanonical_artifact",
                "readModelCoverage must be sparse positive-only (no false)",
                path=f"{path}/{key}",
            )
        if value is not True:
            _fail(
                "remote_state.noncanonical_artifact",
                "readModelCoverage markers must be true when present",
                path=f"{path}/{key}",
            )
    relationships = mapping.get(READ_MODEL_COVERAGE_GOVERNANCE_RELATIONSHIPS) or {}
    return ReadModelCoverageV3(
        data_assets=mapping.get(READ_MODEL_COVERAGE_DATA_ASSETS) is True,
        data_columns=mapping.get(READ_MODEL_COVERAGE_DATA_COLUMNS) is True,
        relationship_data_product_to_data_asset=(
            relationships.get(RELATIONSHIP_FAMILY_DATA_PRODUCT_TO_DATA_ASSET) is True
        ),
        relationship_glossary_term_to_data_asset=(
            relationships.get(RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_ASSET) is True
        ),
        relationship_glossary_term_to_data_column=(
            relationships.get(RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_COLUMN) is True
        ),
    )


def _target_context(raw: object, *, path: str) -> RemoteTargetContextV3:
    mapping = _mapping(raw, path=path)
    surface = _str(mapping.get("surface"), path=f"{path}/surface")
    tenant_id = _str(mapping.get("tenantId"), path=f"{path}/tenantId")
    endpoint = _str(mapping.get("endpoint"), path=f"{path}/endpoint")
    identity = _str(mapping.get("identity"), path=f"{path}/identity")
    if surface != "unifiedCatalog":
        _fail(
            "remote_state.invalid_schema",
            "targetContext.surface must be unifiedCatalog",
            path=f"{path}/surface",
        )
    expected = compute_target_context_identity_v3(
        surface=surface,
        tenant_id=tenant_id,
        endpoint=endpoint,
    )
    if identity != expected:
        _fail(
            "remote_state.identity_mismatch",
            "targetContext.identity does not match recomputed identity",
            path=f"{path}/identity",
        )
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=tenant_id,
        endpoint=endpoint,
        identity=identity,
    )


def _array_presence(document: dict[str, Any], *, key: str, required: bool) -> list[Any]:
    present = key in document
    if required and not present:
        _fail(
            "remote_state.noncanonical_artifact",
            f"{key} is required by capture markers/coverage",
            path=f"/{key}",
        )
    if (not required) and present:
        _fail(
            "remote_state.noncanonical_artifact",
            f"{key} must be absent when not enabled by markers/coverage",
            path=f"/{key}",
        )
    if not present:
        return []
    return _list(document[key], path=f"/{key}")


def _validate_markers(markers: tuple[str, ...]) -> None:
    if not markers:
        return
    if markers not in VALID_CAPTURE_MARKERS:
        _fail(
            "remote_state.noncanonical_artifact",
            "capturedResourceTypes is not a supported capture marker combination",
            path="/capturedResourceTypes",
        )
    if markers[0] != CAPTURED_RESOURCE_TYPE_BUSINESS_DOMAIN:
        _fail(
            "remote_state.noncanonical_artifact",
            "capturedResourceTypes must begin with businessDomain",
            path="/capturedResourceTypes",
        )


def load_remote_state_v3_text(text: str) -> RemoteStateV3:
    """Load and strictly validate a purview-remote-state/v3 JSON artifact."""
    try:
        parsed = json.loads(text, object_pairs_hook=_object_pairs_hook)
    except _DuplicateKeyError:
        _fail("remote_state.duplicate_key", "duplicate object keys are not allowed")
    except json.JSONDecodeError:
        _fail("remote_state.invalid_syntax", "remote-state document is not valid JSON")

    if not isinstance(parsed, dict):
        _fail("remote_state.invalid_syntax", "remote-state document must be a JSON object")
    document: dict[str, Any] = parsed

    if document.get("apiVersion") != REMOTE_STATE_API_VERSION_V3:
        _fail(
            "remote_state.unsupported_version",
            "unsupported or missing remote-state apiVersion for v3 loader",
            path="/apiVersion",
        )

    schema_ok = True
    try:
        Draft202012Validator(load_remote_state_v3_schema()).validate(document)
    except Exception:
        schema_ok = False
    if not schema_ok:
        _fail(
            "remote_state.invalid_schema",
            "remote-state document failed schema validation",
        )

    target_context = _target_context(document.get("targetContext"), path="/targetContext")
    stored_identity = _str(document.get("materialStateIdentity"), path="/materialStateIdentity")

    raw_markers = document.get("capturedResourceTypes")
    if raw_markers is None:
        markers: tuple[str, ...] = ()
    else:
        markers = tuple(
            _str(item, path="/capturedResourceTypes")
            for item in _list(raw_markers, path="/capturedResourceTypes")
        )
    _validate_markers(markers)

    include_dp = CAPTURED_RESOURCE_TYPE_DATA_PRODUCT in markers
    include_gt = CAPTURED_RESOURCE_TYPE_GLOSSARY_TERM in markers

    business_domains = tuple(
        _normalized_business_domain(item, path=f"/businessDomains/{index}")
        for index, item in enumerate(
            _list(document.get("businessDomains"), path="/businessDomains")
        )
    )
    uninterpreted_business_domains = tuple(
        _uninterpreted_business_domain(item, path=f"/uninterpretedBusinessDomains/{index}")
        for index, item in enumerate(
            _list(
                document.get("uninterpretedBusinessDomains"),
                path="/uninterpretedBusinessDomains",
            )
        )
    )

    data_products = tuple(
        _normalized_data_product(item, path=f"/dataProducts/{index}")
        for index, item in enumerate(
            _array_presence(document, key="dataProducts", required=include_dp)
        )
    )
    uninterpreted_data_products = tuple(
        _uninterpreted_data_product(item, path=f"/uninterpretedDataProducts/{index}")
        for index, item in enumerate(
            _array_presence(document, key="uninterpretedDataProducts", required=include_dp)
        )
    )
    glossary_terms = tuple(
        _normalized_glossary_term(item, path=f"/glossaryTerms/{index}")
        for index, item in enumerate(
            _array_presence(document, key="glossaryTerms", required=include_gt)
        )
    )
    uninterpreted_glossary_terms = tuple(
        _uninterpreted_glossary_term(item, path=f"/uninterpretedGlossaryTerms/{index}")
        for index, item in enumerate(
            _array_presence(document, key="uninterpretedGlossaryTerms", required=include_gt)
        )
    )

    coverage_raw = document.get("readModelCoverage")
    coverage: ReadModelCoverageV3 | None
    if coverage_raw is None:
        coverage = None
    else:
        coverage = _read_model_coverage(coverage_raw, path="/readModelCoverage")

    include_da = coverage is not None and coverage.data_assets
    include_dc = coverage is not None and coverage.data_columns
    include_rel = coverage is not None and coverage.includes_governance_relationships

    data_assets = tuple(
        _normalized_data_asset(item, path=f"/dataAssets/{index}")
        for index, item in enumerate(
            _array_presence(document, key="dataAssets", required=include_da)
        )
    )
    uninterpreted_data_assets = tuple(
        _uninterpreted_data_asset(item, path=f"/uninterpretedDataAssets/{index}")
        for index, item in enumerate(
            _array_presence(document, key="uninterpretedDataAssets", required=include_da)
        )
    )
    data_columns = tuple(
        _normalized_data_column(item, path=f"/dataColumns/{index}")
        for index, item in enumerate(
            _array_presence(document, key="dataColumns", required=include_dc)
        )
    )
    uninterpreted_data_columns = tuple(
        _uninterpreted_data_column(item, path=f"/uninterpretedDataColumns/{index}")
        for index, item in enumerate(
            _array_presence(document, key="uninterpretedDataColumns", required=include_dc)
        )
    )
    governance_relationships = tuple(
        _normalized_relationship(item, path=f"/governanceRelationships/{index}")
        for index, item in enumerate(
            _array_presence(document, key="governanceRelationships", required=include_rel)
        )
    )
    uninterpreted_governance_relationships = tuple(
        _uninterpreted_relationship(item, path=f"/uninterpretedGovernanceRelationships/{index}")
        for index, item in enumerate(
            _array_presence(
                document,
                key="uninterpretedGovernanceRelationships",
                required=include_rel,
            )
        )
    )

    if coverage is not None:
        if coverage.relationship_data_product_to_data_asset and not include_dp:
            _fail(
                "remote_state.noncanonical_artifact",
                "dataProductToDataAsset coverage requires dataProduct capture",
                path="/readModelCoverage",
            )
        if (
            coverage.relationship_glossary_term_to_data_asset
            or coverage.relationship_glossary_term_to_data_column
        ) and not include_gt:
            _fail(
                "remote_state.noncanonical_artifact",
                "glossaryTerm relationship coverage requires glossaryTerm capture",
                path="/readModelCoverage",
            )
        if coverage.data_columns and not coverage.data_assets:
            _fail(
                "remote_state.noncanonical_artifact",
                "dataColumns coverage requires dataAssets coverage",
                path="/readModelCoverage",
            )

    try:
        loaded = build_remote_state_v3(
            business_domains,
            uninterpreted_business_domains,
            target_context,
            data_products=data_products,
            uninterpreted_data_products=uninterpreted_data_products,
            glossary_terms=glossary_terms,
            uninterpreted_glossary_terms=uninterpreted_glossary_terms,
            captured_resource_types=markers,
            data_assets=data_assets,
            uninterpreted_data_assets=uninterpreted_data_assets,
            data_columns=data_columns,
            uninterpreted_data_columns=uninterpreted_data_columns,
            governance_relationships=governance_relationships,
            uninterpreted_governance_relationships=uninterpreted_governance_relationships,
            read_model_coverage=coverage,
        )
    except RemoteStateError:
        raise
    except Exception:
        _fail(
            "remote_state.noncanonical_artifact",
            "remote-state document could not be materialized canonically",
        )

    recomputed = compute_material_state_identity(loaded.identity_document())
    if recomputed != stored_identity or loaded.material_state_identity != stored_identity:
        _fail(
            "remote_state.identity_mismatch",
            "materialStateIdentity does not match recomputed identity",
            path="/materialStateIdentity",
        )

    if loaded.to_document() != document:
        _fail(
            "remote_state.noncanonical_artifact",
            "remote-state document is not in canonical form",
        )
    return loaded


def load_remote_state_v3_file(path: str | Path) -> RemoteStateV3:
    """Load a remote-state/v3 artifact from a UTF-8 JSON file."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        _fail("remote_state.invalid_syntax", "remote-state file could not be read")
    return load_remote_state_v3_text(text)
