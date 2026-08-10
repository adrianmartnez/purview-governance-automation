"""Deterministic read-only desired-vs-remote multi-resource diff."""

from purview_governance.diff.models import DiffDocument, DiffItem, DiffReason
from purview_governance.diff.service import diff_desired_vs_remote, diff_desired_vs_remote_v2

__all__ = [
    "DiffDocument",
    "DiffItem",
    "DiffReason",
    "diff_desired_vs_remote",
    "diff_desired_vs_remote_v2",
]
