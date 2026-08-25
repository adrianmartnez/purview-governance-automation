"""Strict loader roundtrip and tamper detection for purview-remote-state/v3."""

from __future__ import annotations

import json

import pytest

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.loader_v3 import load_remote_state_v3_text
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    NormalizedDataProduct,
    NormalizedGlossaryTerm,
    RemoteTargetContextV3,
    build_remote_state_v3,
)
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT

TENANT = "20000000-0000-4000-8000-000000000001"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
PRODUCT_A = "40000000-0000-4000-8000-000000000001"
TERM_A = "50000000-0000-4000-8000-000000000001"
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


def _domain() -> NormalizedBusinessDomain:
    return NormalizedBusinessDomain(
        id=DOMAIN_A,
        properties={
            "name": "root-domain",
            "status": "PUBLISHED",
            "type": "DataDomain",
        },
    )


def _product() -> NormalizedDataProduct:
    return NormalizedDataProduct(
        id=PRODUCT_A,
        properties={
            "name": "sales-product",
            "domain": DOMAIN_A,
            "type": "Master",
            "description": "Product description",
            "businessUse": "Primary business use",
            "owners": [{"id": OWNER_A}],
        },
        safety_properties={"status": "DRAFT"},
    )


def _term() -> NormalizedGlossaryTerm:
    return NormalizedGlossaryTerm(
        id=TERM_A,
        properties={
            "name": "revenue",
            "domain": DOMAIN_A,
            "description": "Revenue term",
            "owners": [{"id": OWNER_A}],
        },
        safety_properties={"status": "DRAFT"},
    )


def _assert_roundtrip(state) -> None:
    text = state.to_canonical_json()
    loaded = load_remote_state_v3_text(text)
    assert loaded.to_canonical_json() == text
    assert loaded.material_state_identity == state.material_state_identity


def test_shape_a_roundtrip() -> None:
    state = build_remote_state_v3((_domain(),), (), _target())
    doc = state.to_document()
    assert "capturedResourceTypes" not in doc
    assert "dataProducts" not in doc
    assert "glossaryTerms" not in doc
    _assert_roundtrip(state)


def test_shape_b_roundtrip() -> None:
    state = build_remote_state_v3(
        (_domain(),),
        (),
        _target(),
        data_products=(_product(),),
        captured_resource_types=("businessDomain", "dataProduct"),
    )
    doc = state.to_document()
    assert doc["capturedResourceTypes"] == ["businessDomain", "dataProduct"]
    assert "dataProducts" in doc
    assert "glossaryTerms" not in doc
    _assert_roundtrip(state)


def test_shape_c_roundtrip() -> None:
    state = build_remote_state_v3(
        (_domain(),),
        (),
        _target(),
        glossary_terms=(_term(),),
        captured_resource_types=("businessDomain", "glossaryTerm"),
    )
    doc = state.to_document()
    assert doc["capturedResourceTypes"] == ["businessDomain", "glossaryTerm"]
    assert "glossaryTerms" in doc
    assert "dataProducts" not in doc
    _assert_roundtrip(state)


def test_shape_d_roundtrip() -> None:
    state = build_remote_state_v3(
        (_domain(),),
        (),
        _target(),
        data_products=(_product(),),
        glossary_terms=(_term(),),
        captured_resource_types=("businessDomain", "dataProduct", "glossaryTerm"),
    )
    doc = state.to_document()
    assert doc["capturedResourceTypes"] == [
        "businessDomain",
        "dataProduct",
        "glossaryTerm",
    ]
    assert "dataProducts" in doc
    assert "glossaryTerms" in doc
    _assert_roundtrip(state)


def test_material_identity_tamper_rejected() -> None:
    state = build_remote_state_v3((_domain(),), (), _target())
    document = state.to_document()
    document["materialStateIdentity"] = "sha256:" + ("a" * 64)
    with pytest.raises(RemoteStateError) as exc_info:
        load_remote_state_v3_text(json.dumps(document))
    assert exc_info.value.code == "remote_state.identity_mismatch"


def test_target_identity_tamper_rejected() -> None:
    state = build_remote_state_v3((_domain(),), (), _target())
    document = state.to_document()
    document["targetContext"]["identity"] = "sha256:" + ("b" * 64)
    with pytest.raises(RemoteStateError) as exc_info:
        load_remote_state_v3_text(json.dumps(document))
    assert exc_info.value.code == "remote_state.identity_mismatch"


def test_shape_b_missing_data_products_array_rejected() -> None:
    state = build_remote_state_v3(
        (_domain(),),
        (),
        _target(),
        data_products=(),
        captured_resource_types=("businessDomain", "dataProduct"),
    )
    document = state.to_document()
    del document["dataProducts"]
    with pytest.raises(RemoteStateError) as exc_info:
        load_remote_state_v3_text(json.dumps(document, separators=(",", ":")))
    assert exc_info.value.code in {
        "remote_state.noncanonical_artifact",
        "remote_state.invalid_schema",
    }


def test_domain_property_tamper_without_identity_refresh_rejected() -> None:
    state = build_remote_state_v3((_domain(),), (), _target())
    document = state.to_document()
    document["businessDomains"][0]["properties"]["name"] = "tampered-name"
    with pytest.raises(RemoteStateError) as exc_info:
        load_remote_state_v3_text(json.dumps(document, separators=(",", ":")))
    assert exc_info.value.code == "remote_state.identity_mismatch"
