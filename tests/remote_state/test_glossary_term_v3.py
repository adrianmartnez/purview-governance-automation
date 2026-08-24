"""Glossary Term remote-state v3 normalization tests."""

from __future__ import annotations

from jsonschema import Draft202012Validator

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.glossary_term_normalize import normalize_glossary_term
from purview_governance.remote_state.glossary_term_policy import (
    REASON_DUPLICATE_ACRONYM,
    REASON_INVALID_ACRONYMS,
    REASON_INVALID_PARENT_ID,
)
from purview_governance.remote_state.models_v3 import (
    NormalizedGlossaryTerm,
    RemoteTargetContextV3,
    UninterpretedGlossaryTerm,
    build_remote_state_v3,
)
from purview_governance.remote_state.schema import load_remote_state_v3_schema
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOMAIN_ID = "10000000-0000-4000-8000-000000000001"
TERM_ID = "50000000-0000-4000-8000-000000000001"
PARENT_ID = "50000000-0000-4000-8000-000000000002"
OWNER_A = "30000000-0000-4000-8000-000000000001"


def _target() -> RemoteTargetContextV3:
    endpoint = UNIFIED_CATALOG_PRODUCTION_ENDPOINT
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=TENANT,
        endpoint=endpoint,
        identity=compute_target_context_identity_v3(
            surface="unifiedCatalog",
            tenant_id=TENANT,
            endpoint=endpoint,
        ),
    )


def _raw_term(**overrides: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "id": TERM_ID,
        "name": "revenue",
        "domain": DOMAIN_ID,
        "description": "Revenue term",
        "status": "DRAFT",
        "contacts": {"owner": [{"id": OWNER_A}]},
    }
    raw.update(overrides)
    return raw


def test_normalize_root_term_without_parent_or_acronyms() -> None:
    result = normalize_glossary_term(_raw_term())
    assert isinstance(result, NormalizedGlossaryTerm)
    assert "parentId" not in result.properties
    assert "acronyms" not in result.properties


def test_normalize_parent_id_null_is_uninterpreted() -> None:
    result = normalize_glossary_term(_raw_term(parentId=None))
    assert isinstance(result, UninterpretedGlossaryTerm)
    assert result.reason_code == REASON_INVALID_PARENT_ID


def test_normalize_parent_id_invalid_uuid_is_uninterpreted() -> None:
    result = normalize_glossary_term(_raw_term(parentId="not-a-uuid"))
    assert isinstance(result, UninterpretedGlossaryTerm)
    assert result.reason_code == REASON_INVALID_PARENT_ID


def test_normalize_acronyms_null_is_uninterpreted() -> None:
    result = normalize_glossary_term(_raw_term(acronyms=None))
    assert isinstance(result, UninterpretedGlossaryTerm)
    assert result.reason_code == REASON_INVALID_ACRONYMS


def test_normalize_duplicate_acronym_is_uninterpreted() -> None:
    result = normalize_glossary_term(_raw_term(acronyms=["REV", "REV"]))
    assert isinstance(result, UninterpretedGlossaryTerm)
    assert result.reason_code == REASON_DUPLICATE_ACRONYM


def test_normalize_acronyms_are_sorted() -> None:
    result = normalize_glossary_term(_raw_term(acronyms=["ZZZ", "AAA"]))
    assert isinstance(result, NormalizedGlossaryTerm)
    assert result.properties["acronyms"] == ["AAA", "ZZZ"]


def test_remote_state_shape_c_schema_validation() -> None:
    term = normalize_glossary_term(_raw_term(acronyms=["REV"]))
    assert isinstance(term, NormalizedGlossaryTerm)
    state = build_remote_state_v3(
        (),
        (),
        _target(),
        glossary_terms=(term,),
        captured_resource_types=("businessDomain", "glossaryTerm"),
    )
    schema = load_remote_state_v3_schema()
    Draft202012Validator(schema).validate(state.to_document())


def test_remote_state_shape_d_schema_validation() -> None:
    term = normalize_glossary_term(_raw_term(parentId=PARENT_ID))
    assert isinstance(term, NormalizedGlossaryTerm)
    parent = normalize_glossary_term(_raw_term(id=PARENT_ID, name="parent-term"))
    assert isinstance(parent, NormalizedGlossaryTerm)
    state = build_remote_state_v3(
        (),
        (),
        _target(),
        glossary_terms=(parent, term),
        captured_resource_types=("businessDomain", "dataProduct", "glossaryTerm"),
    )
    schema = load_remote_state_v3_schema()
    Draft202012Validator(schema).validate(state.to_document())
