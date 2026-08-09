"""Stable property-level and safety reason builders for diff."""

from __future__ import annotations

from purview_governance.diff.models import DiffReason


def sort_reasons(reasons: list[DiffReason]) -> tuple[DiffReason, ...]:
    return tuple(sorted(reasons, key=lambda item: (item.path, item.code)))


def reason(
    code: str,
    path: str,
    *,
    before: str | None = None,
    after: str | None = None,
) -> DiffReason:
    return DiffReason(code=code, path=path, before=before, after=after)
