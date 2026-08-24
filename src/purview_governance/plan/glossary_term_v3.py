"""Glossary Term plan-time dependency and hierarchy validation (v3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from purview_governance.desired.models_v3 import GlossaryTermDesiredState
from purview_governance.diff.models_v3 import (
    DiffGlossaryTermItem,
)
from purview_governance.diff.reasons import reason, sort_reasons
from purview_governance.remote_state.models_v3 import RemoteStateV3

_UNRESOLVED = object()


@dataclass(frozen=True, slots=True)
class _ParentResolution:
    status: Literal["satisfied", "depends_on_create", "blocked"]
    reason_code: str | None = None


def _normalized_term_ids(remote: RemoteStateV3) -> set[str]:
    return {term.id for term in remote.glossary_terms}


def _uninterpreted_term_ids(remote: RemoteStateV3) -> set[str]:
    return {item.id for item in remote.uninterpreted_glossary_terms if item.id is not None}


def _remote_term_domain(remote: RemoteStateV3, term_id: str) -> str | None:
    for term in remote.glossary_terms:
        if term.id == term_id:
            return term.properties["domain"]
    return None


def _gt_create_eligible(change_set, term_id: str) -> bool:
    for item in change_set.items:
        if isinstance(item, DiffGlossaryTermItem) and item.id == term_id:
            return item.outcome == "create"
    return False


def _gt_create_blocked(change_set, term_id: str) -> bool:
    for item in change_set.items:
        if isinstance(item, DiffGlossaryTermItem) and item.id == term_id:
            return item.outcome == "blocked"
    return False


def _resolve_glossary_term_parent(
    parent_id: str,
    *,
    remote: RemoteStateV3,
    change_set,
    desired_term_ids: set[str],
) -> _ParentResolution:
    if parent_id in _normalized_term_ids(remote):
        return _ParentResolution(status="satisfied")
    if parent_id in _uninterpreted_term_ids(remote):
        return _ParentResolution(
            status="blocked",
            reason_code="plan.glossary_term_parent_uninterpreted",
        )
    if parent_id in desired_term_ids:
        if _gt_create_eligible(change_set, parent_id):
            return _ParentResolution(status="depends_on_create")
        if _gt_create_blocked(change_set, parent_id):
            return _ParentResolution(
                status="blocked",
                reason_code="plan.glossary_term_parent_dependency_blocked",
            )
        return _ParentResolution(
            status="blocked",
            reason_code="plan.glossary_term_parent_unresolved",
        )
    return _ParentResolution(
        status="blocked",
        reason_code="plan.glossary_term_parent_unresolved",
    )


def _block_glossary_term(
    item: DiffGlossaryTermItem,
    *,
    reason_code: str,
    path: str = "/",
) -> DiffGlossaryTermItem:
    reasons = list(item.reasons)
    reasons.append(reason(reason_code, path))
    return DiffGlossaryTermItem(
        id=item.id,
        resource_type="glossaryTerm",
        outcome="blocked",
        reasons=sort_reasons(reasons),
    )


def _resultant_parent(
    term_id: str,
    *,
    desired_parent_by_id: dict[str, str | None],
    remote: RemoteStateV3,
) -> str | None | object:
    if term_id in desired_parent_by_id:
        return desired_parent_by_id[term_id]
    for term in remote.glossary_terms:
        if term.id == term_id:
            props = term.properties
            if "parentId" not in props:
                return None
            return props["parentId"]
    if term_id in _uninterpreted_term_ids(remote):
        return _UNRESOLVED
    return _UNRESOLVED


def _validate_desired_term_hierarchy(
    term: GlossaryTermDesiredState,
    *,
    desired_parent_by_id: dict[str, str | None],
    desired_domain_by_id: dict[str, str],
    remote: RemoteStateV3,
) -> str | None:
    """Return blocking reason code if hierarchy invalid for this desired term, else None."""
    visited: set[str] = set()
    current: str | None = term.id
    child_domain = term.domain

    while current is not None:
        if current in visited:
            return "plan.glossary_term_hierarchy_cycle"
        visited.add(current)

        parent = _resultant_parent(
            current,
            desired_parent_by_id=desired_parent_by_id,
            remote=remote,
        )
        if parent is _UNRESOLVED:
            if current == term.id and term.parent_id is not None:
                return "plan.glossary_term_parent_unresolved"
            return "plan.glossary_term_parent_unresolved"

        if parent is None:
            break

        if current == term.id:
            parent_domain = desired_domain_by_id.get(parent)
            if parent_domain is None:
                parent_domain = _remote_term_domain(remote, parent)
            if parent_domain is None:
                return "plan.glossary_term_parent_unresolved"
            if parent_domain != child_domain:
                return "plan.glossary_term_parent_domain_mismatch"
        else:
            current_domain = desired_domain_by_id.get(current)
            if current_domain is None:
                current_domain = _remote_term_domain(remote, current)
            parent_domain = desired_domain_by_id.get(parent)
            if parent_domain is None:
                parent_domain = _remote_term_domain(remote, parent)
            if current_domain is None or parent_domain is None:
                return "plan.glossary_term_parent_unresolved"
            if current_domain != parent_domain:
                return "plan.glossary_term_parent_domain_mismatch"

        current = parent

    return None


def enforce_glossary_term_dependencies(
    items: list[DiffGlossaryTermItem],
    *,
    desired_terms: tuple[GlossaryTermDesiredState, ...],
    remote: RemoteStateV3,
    change_set,
    desired_domain_ids: set[str],
    resolve_domain,
) -> list[DiffGlossaryTermItem]:
    desired_term_ids = {term.id for term in desired_terms}
    desired_parent_by_id = {term.id: term.parent_id for term in desired_terms}
    desired_domain_by_id = {term.id: term.domain for term in desired_terms}
    domain_by_term = {term.id: term.domain for term in desired_terms}
    parent_by_term = {term.id: term.parent_id for term in desired_terms}

    updated: list[DiffGlossaryTermItem] = []
    for item in items:
        if item.outcome not in {"create", "replace"}:
            updated.append(item)
            continue

        blocked_reason: str | None = None

        domain_id = domain_by_term.get(item.id)
        if domain_id is not None:
            domain_resolution = resolve_domain(
                domain_id,
                remote=remote,
                change_set=change_set,
                desired_domain_ids=desired_domain_ids,
            )
            if domain_resolution.status == "blocked":
                blocked_reason = domain_resolution.reason_code or "plan.domain_unresolved"

        if blocked_reason is None:
            parent_id = parent_by_term.get(item.id)
            if parent_id is not None:
                parent_resolution = _resolve_glossary_term_parent(
                    parent_id,
                    remote=remote,
                    change_set=change_set,
                    desired_term_ids=desired_term_ids,
                )
                if parent_resolution.status == "blocked":
                    blocked_reason = (
                        parent_resolution.reason_code or "plan.glossary_term_parent_unresolved"
                    )

        if blocked_reason is None:
            term = next(t for t in desired_terms if t.id == item.id)
            hierarchy_reason = _validate_desired_term_hierarchy(
                term,
                desired_parent_by_id=desired_parent_by_id,
                desired_domain_by_id=desired_domain_by_id,
                remote=remote,
            )
            if hierarchy_reason is not None:
                blocked_reason = hierarchy_reason

        if blocked_reason is not None:
            path = (
                "/properties/parentId"
                if blocked_reason.startswith("plan.glossary_term_parent")
                or blocked_reason.startswith("plan.glossary_term_hierarchy")
                else "/properties/domain"
            )
            updated.append(_block_glossary_term(item, reason_code=blocked_reason, path=path))
        else:
            updated.append(item)

    return updated
