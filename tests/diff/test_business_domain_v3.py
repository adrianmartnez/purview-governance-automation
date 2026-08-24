"""Tests for Business Domain diff (v3)."""

from __future__ import annotations

from purview_governance.desired.models_v3 import BusinessDomainDesiredState, DesiredStateV3
from purview_governance.diff.business_domain import diff_desired_vs_remote_v3
from purview_governance.diff.models_v3 import DiffBusinessDomainItem
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.models import UnsupportedConfigurableField
from purview_governance.remote_state.models_v3 import (
    NormalizedBusinessDomain,
    RemoteStateV3,
    RemoteTargetContextV3,
    UninterpretedBusinessDomain,
    build_remote_state_v3,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
ENDPOINT = "https://catalog.purview.azure.com"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
DOMAIN_C = "10000000-0000-4000-8000-000000000003"


def _target_context() -> RemoteTargetContextV3:
    identity = compute_target_context_identity_v3(
        surface="unifiedCatalog",
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
    )
    return RemoteTargetContextV3(
        surface="unifiedCatalog",
        tenant_id=TENANT_ID,
        endpoint=ENDPOINT,
        identity=identity,
    )


def _remote(
    *,
    domains: tuple[NormalizedBusinessDomain, ...] = (),
    uninterpreted: tuple[UninterpretedBusinessDomain, ...] = (),
) -> RemoteStateV3:
    return build_remote_state_v3(domains, uninterpreted, _target_context())


def _desired(*domains: BusinessDomainDesiredState) -> DesiredStateV3:
    return DesiredStateV3(business_domains=tuple(sorted(domains, key=lambda d: d.id)))


def _normalized(
    domain_id: str,
    name: str,
    *,
    parent_id: str | None = None,
    description: str | None = None,
    unsupported: tuple[UnsupportedConfigurableField, ...] = (),
) -> NormalizedBusinessDomain:
    props: dict[str, object] = {
        "name": name,
        "status": "PUBLISHED",
        "type": "DataDomain",
    }
    if description is not None:
        props["description"] = description
    if parent_id is not None:
        props["parentId"] = parent_id
    return NormalizedBusinessDomain(
        id=domain_id,
        properties=props,
        unsupported_configurable_fields=unsupported,
    )


def _item(change_set, domain_id: str) -> DiffBusinessDomainItem:
    for item in change_set.items:
        if isinstance(item, DiffBusinessDomainItem) and item.id == domain_id:
            return item
    raise AssertionError(f"missing diff item for {domain_id}")


def test_create_no_op_replace_remote_only_and_blocked() -> None:
    desired = _desired(
        BusinessDomainDesiredState(
            id=DOMAIN_A,
            name="root-domain",
            description=None,
            parent_id=None,
            status="PUBLISHED",
            domain_type="DataDomain",
        ),
        BusinessDomainDesiredState(
            id=DOMAIN_B,
            name="new-child",
            description=None,
            parent_id=DOMAIN_A,
            status="DRAFT",
            domain_type="FunctionalUnit",
        ),
        BusinessDomainDesiredState(
            id=DOMAIN_C,
            name="conflict-name",
            description=None,
            parent_id=None,
            status="PUBLISHED",
            domain_type="DataDomain",
        ),
    )
    remote = _remote(
        domains=(
            _normalized(DOMAIN_A, "root-domain"),
            _normalized("10000000-0000-4000-8000-000000000099", "conflict-name"),
        ),
    )
    change_set = diff_desired_vs_remote_v3(desired, remote)

    assert _item(change_set, DOMAIN_A).outcome == "no-op"
    assert _item(change_set, DOMAIN_B).outcome == "create"
    assert _item(change_set, DOMAIN_C).outcome == "blocked"
    assert _item(change_set, "10000000-0000-4000-8000-000000000099").outcome == "remote-only"


def test_replace_on_property_change_and_description_semantics() -> None:
    desired = _desired(
        BusinessDomainDesiredState(
            id=DOMAIN_A,
            name="renamed-root",
            description="",
            parent_id=None,
            status="DRAFT",
            domain_type="LineOfBusiness",
            is_restricted=True,
        ),
    )
    remote = _remote(domains=(_normalized(DOMAIN_A, "root-domain"),))
    change_set = diff_desired_vs_remote_v3(desired, remote)
    item = _item(change_set, DOMAIN_A)
    assert item.outcome == "replace"
    codes = {reason.code for reason in item.reasons}
    assert "properties.name.changed" in codes
    assert "properties.description.changed" in codes
    assert "properties.status.changed" in codes
    assert "properties.type.changed" in codes
    assert "properties.isRestricted.changed" in codes


def test_blocked_on_unsupported_configurable() -> None:
    desired = _desired(
        BusinessDomainDesiredState(
            id=DOMAIN_A,
            name="root-domain",
            description=None,
            parent_id=None,
            status="PUBLISHED",
            domain_type="DataDomain",
        ),
    )
    remote = _remote(
        domains=(
            _normalized(
                DOMAIN_A,
                "root-domain",
                unsupported=(
                    UnsupportedConfigurableField(
                        path="/managedAttributes",
                        value_identity="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    ),
                ),
            ),
        ),
    )
    change_set = diff_desired_vs_remote_v3(desired, remote)
    item = _item(change_set, DOMAIN_A)
    assert item.outcome == "blocked"
    assert any(reason.code == "remote.unsupported_configurable_field" for reason in item.reasons)
