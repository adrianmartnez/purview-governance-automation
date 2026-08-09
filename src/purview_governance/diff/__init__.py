"""Deterministic read-only desired-vs-remote Data Source diff."""

from purview_governance.diff.models import DiffDocument, DiffItem, DiffReason
from purview_governance.diff.service import diff_desired_vs_remote

__all__ = [
    "DiffDocument",
    "DiffItem",
    "DiffReason",
    "diff_desired_vs_remote",
]
