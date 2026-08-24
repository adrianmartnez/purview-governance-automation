"""Tests for Glossary Term diff (v3)."""

from __future__ import annotations

from purview_governance.desired.models_v3 import (
    DesiredStateV3,
    GlossaryTermDesiredState,
    GlossaryTermOwnerDesiredState,
)
from purview_governance.diff.glossary_term import diff_glossary_terms
from purview_governance.plan.identity import compute_target_context_identity_v3
from purview_governance.remote_state.models_v3 import (
    NormalizedGlossaryTerm,
    RemoteTargetContextV3,
    build_remote_state_v3,
)

TENANT_ID = "20000000-0000-4000-8000-000000000001"
ENDPOINT = "https://catalog.purview.azure.com"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
GT_A = "50000000-0000-4000-8000-000000000001"
OWNER_A = "30000000-0000-4000-8000-000000000001"


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


def _remote(*terms: NormalizedGlossaryTerm) -> build_remote_state_v3:
    return build_remote_state_v3(
        (),
        (),
        _target_context(),
        glossary_terms=terms,
        captured_resource_types=("businessDomain", "glossaryTerm"),
    )


def _term_desired(
    *,
    term_id: str = GT_A,
    parent_id: str | None = None,
    acronyms: tuple[str, ...] | None = None,
) -> GlossaryTermDesiredState:
    return GlossaryTermDesiredState(
        id=term_id,
        name="revenue",
        domain=DOMAIN_A,
        description="Revenue term",
        owners=(GlossaryTermOwnerDesiredState(id=OWNER_A),),
        parent_id=parent_id,
        acronyms=acronyms,
    )


def _normalized(
    *,
    parent_id: str | None = None,
    acronyms: list[str] | None = None,
    status: str = "DRAFT",
) -> NormalizedGlossaryTerm:
    properties: dict[str, object] = {
        "name": "revenue",
        "domain": DOMAIN_A,
        "description": "Revenue term",
        "owners": [{"id": OWNER_A}],
    }
    if parent_id is not None:
        properties["parentId"] = parent_id
    if acronyms is not None:
        properties["acronyms"] = acronyms
    return NormalizedGlossaryTerm(
        id=GT_A,
        properties=properties,
        safety_properties={"status": status},
    )


def _item(items, term_id: str = GT_A):
    for item in items:
        if item.id == term_id:
            return item
    raise AssertionError(f"missing glossary term item {term_id}")


def test_parent_removal_when_remote_has_parent() -> None:
    desired = DesiredStateV3(glossary_terms=(_term_desired(parent_id=None),))
    remote = _remote(_normalized(parent_id="50000000-0000-4000-8000-000000000099"))
    items = diff_glossary_terms(desired, remote)
    item = _item(items)
    assert item.outcome == "replace"
    assert any(reason.code == "properties.parentId.changed" for reason in item.reasons)


def test_parent_no_op_when_both_absent() -> None:
    desired = DesiredStateV3(glossary_terms=(_term_desired(parent_id=None),))
    remote = _remote(_normalized())
    items = diff_glossary_terms(desired, remote)
    assert _item(items).outcome == "no-op"


def test_acronyms_absent_does_not_drift_when_remote_has_values() -> None:
    desired = DesiredStateV3(glossary_terms=(_term_desired(acronyms=None),))
    remote = _remote(_normalized(acronyms=["REV"]))
    items = diff_glossary_terms(desired, remote)
    assert _item(items).outcome == "no-op"
    assert not any(reason.code == "properties.acronyms.changed" for reason in _item(items).reasons)


def test_acronyms_empty_explicit_clear() -> None:
    desired = DesiredStateV3(glossary_terms=(_term_desired(acronyms=()),))
    remote = _remote(_normalized(acronyms=["REV"]))
    items = diff_glossary_terms(desired, remote)
    item = _item(items)
    assert item.outcome == "replace"
    assert any(reason.code == "properties.acronyms.changed" for reason in item.reasons)


def test_acronyms_reordered_is_no_op() -> None:
    desired = DesiredStateV3(glossary_terms=(_term_desired(acronyms=("AAA", "ZZZ")),))
    remote = _remote(_normalized(acronyms=["ZZZ", "AAA"]))
    items = diff_glossary_terms(desired, remote)
    assert _item(items).outcome == "no-op"


def test_domain_move_is_blocked() -> None:
    desired = DesiredStateV3(
        glossary_terms=(
            GlossaryTermDesiredState(
                id=GT_A,
                name="revenue",
                domain="10000000-0000-4000-8000-000000000099",
                description="Revenue term",
                owners=(GlossaryTermOwnerDesiredState(id=OWNER_A),),
            ),
        )
    )
    remote = _remote(_normalized())
    items = diff_glossary_terms(desired, remote)
    item = _item(items)
    assert item.outcome == "blocked"
    assert any(
        reason.code == "plan.glossary_term_domain_move_unverified" for reason in item.reasons
    )
