"""Business Domain remote-state v3 normalization tests."""

from __future__ import annotations

from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.business_domain_normalize import normalize_business_domain
from purview_governance.remote_state.canonical import compute_value_identity
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    RemoteTargetContextV3,
    UninterpretedBusinessDomain,
    build_remote_state_v3,
)
from purview_governance.unified_catalog.constants import UNIFIED_CATALOG_PRODUCTION_ENDPOINT

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOMAIN_ID = "7e74f902-62f5-49f4-8258-92ed2b8537ba"


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


def test_normalize_root_domain_without_parent() -> None:
    raw = {
        "id": DOMAIN_ID,
        "name": "sales",
        "status": "PUBLISHED",
        "type": "FunctionalUnit",
    }
    result = normalize_business_domain(raw)
    assert isinstance(result, NormalizedBusinessDomain)
    assert "parentId" not in result.properties


def test_self_parent_uninterpreted() -> None:
    raw = {
        "id": DOMAIN_ID,
        "name": "sales",
        "status": "PUBLISHED",
        "type": "FunctionalUnit",
        "parentId": DOMAIN_ID,
    }
    result = normalize_business_domain(raw)
    assert isinstance(result, UninterpretedBusinessDomain)
    assert result.reason_code == "remote_state.hierarchy_ambiguous"


def test_system_data_does_not_affect_material_identity() -> None:
    base = {
        "id": DOMAIN_ID,
        "name": "sales",
        "status": "PUBLISHED",
        "type": "FunctionalUnit",
    }
    with_ts = {
        **base,
        "systemData": {
            "createdAt": "1970-01-01T00:00:00.000Z",
            "createdBy": "00000000-0000-0000-0000-000000000001",
            "lastModifiedAt": "2020-01-01T00:00:00.000Z",
            "lastModifiedBy": "11111111-1111-1111-1111-111111111111",
        },
    }
    norm_a = normalize_business_domain(base)
    norm_b = normalize_business_domain(with_ts)
    assert isinstance(norm_a, NormalizedBusinessDomain)
    assert isinstance(norm_b, NormalizedBusinessDomain)
    state_a = build_remote_state_v3((norm_a,), (), _target())
    state_b = build_remote_state_v3((norm_b,), (), _target())
    assert state_a.material_state_identity == state_b.material_state_identity


def test_value_identity_object_key_order_invariant() -> None:
    parent_a = {"refName": "ref1", "type": "CollectionReference"}
    parent_b = {"type": "CollectionReference", "refName": "ref1"}
    domains_a = [
        {
            "name": "pd",
            "friendlyName": "PD",
            "relatedCollections": [
                {
                    "name": "rc",
                    "friendlyName": "RC",
                    "parentCollection": parent_a,
                }
            ],
        }
    ]
    domains_b = [
        {
            "friendlyName": "PD",
            "name": "pd",
            "relatedCollections": [
                {
                    "friendlyName": "RC",
                    "name": "rc",
                    "parentCollection": parent_b,
                }
            ],
        }
    ]
    raw_a = {
        "id": DOMAIN_ID,
        "name": "sales",
        "status": "PUBLISHED",
        "type": "FunctionalUnit",
        "domains": domains_a,
    }
    raw_b = {**raw_a, "domains": domains_b}
    norm_a = normalize_business_domain(raw_a)
    norm_b = normalize_business_domain(raw_b)
    assert isinstance(norm_a, NormalizedBusinessDomain)
    assert isinstance(norm_b, NormalizedBusinessDomain)
    assert norm_a.unsupported_configurable_fields[0].value_identity == (
        norm_b.unsupported_configurable_fields[0].value_identity
    )


def test_value_identity_array_order_may_differ() -> None:
    attrs_a = [{"name": "a"}, {"name": "b"}]
    attrs_b = [{"name": "b"}, {"name": "a"}]
    id_a = compute_value_identity(attrs_a)
    id_b = compute_value_identity(attrs_b)
    assert id_a != id_b
