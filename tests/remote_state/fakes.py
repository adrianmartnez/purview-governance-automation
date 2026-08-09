"""Fake read-only Data Source clients for remote-state unit tests."""

from __future__ import annotations

from typing import Any

from purview_governance.scanning.client import DataSourceListResult


class MutationAttemptError(AssertionError):
    """Raised when a read-only fake is asked to mutate."""


class FakeReadClient:
    """In-memory List/Get seam; fails immediately on mutation attempts."""

    def __init__(
        self,
        list_items: list[dict[str, Any]] | None = None,
        get_bodies: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._list_items = list(list_items or [])
        self._get_bodies = dict(get_bodies or {})
        self.list_calls = 0
        self.get_calls: list[str] = []

    def list_data_sources(self) -> DataSourceListResult:
        self.list_calls += 1
        return DataSourceListResult(items=tuple(self._list_items))

    def get_data_source(self, name: str) -> dict[str, Any]:
        self.get_calls.append(name)
        if name not in self._get_bodies:
            msg = f"missing fixture for get_data_source({name!r})"
            raise KeyError(msg)
        return dict(self._get_bodies[name])

    def _create_or_replace_data_source(self, name: str, payload: object) -> dict[str, Any]:
        raise MutationAttemptError("mutation is forbidden on FakeReadClient")

    def __getattr__(self, item: str) -> Any:
        if item in {
            "create_or_replace_data_source",
            "delete_data_source",
            "put",
        }:
            raise MutationAttemptError(f"mutation attribute {item!r} is forbidden")
        msg = f"{type(self).__name__!r} object has no attribute {item!r}"
        raise AttributeError(msg)
