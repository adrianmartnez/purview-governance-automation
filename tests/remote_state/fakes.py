"""Fake read-only Data Source / Scanning clients for remote-state unit tests."""

from __future__ import annotations

from typing import Any

from purview_governance.scanning.client import (
    DataSourceListResult,
    ScanListResult,
    ScanRuleSetListResult,
)


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


class FakeScanningReadClient(FakeReadClient):
    """In-memory DS + Scan + Custom SRS seam for remote-state/v2 capture tests."""

    def __init__(
        self,
        list_items: list[dict[str, Any]] | None = None,
        get_bodies: dict[str, dict[str, Any]] | None = None,
        scan_list_by_parent: dict[str, list[dict[str, Any]]] | None = None,
        scan_get_bodies: dict[tuple[str, str], dict[str, Any]] | None = None,
        scan_ruleset_list_items: list[dict[str, Any]] | None = None,
        scan_ruleset_get_bodies: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(list_items=list_items, get_bodies=get_bodies)
        self._scan_list_by_parent = {
            key: list(value) for key, value in (scan_list_by_parent or {}).items()
        }
        self._scan_get_bodies = dict(scan_get_bodies or {})
        self._scan_ruleset_list_items = list(scan_ruleset_list_items or [])
        self._scan_ruleset_get_bodies = dict(scan_ruleset_get_bodies or {})
        self.list_scan_calls: list[str] = []
        self.get_scan_calls: list[tuple[str, str]] = []
        self.list_scan_ruleset_calls = 0
        self.get_scan_ruleset_calls: list[str] = []

    def list_scans(self, data_source_name: str) -> ScanListResult:
        self.list_scan_calls.append(data_source_name)
        items = self._scan_list_by_parent.get(data_source_name, [])
        return ScanListResult(items=tuple(dict(item) for item in items))

    def get_scan(self, data_source_name: str, scan_name: str) -> dict[str, Any]:
        key = (data_source_name, scan_name)
        self.get_scan_calls.append(key)
        if key not in self._scan_get_bodies:
            msg = f"missing fixture for get_scan({data_source_name!r}, {scan_name!r})"
            raise KeyError(msg)
        return dict(self._scan_get_bodies[key])

    def list_scan_rule_sets(self) -> ScanRuleSetListResult:
        self.list_scan_ruleset_calls += 1
        return ScanRuleSetListResult(
            items=tuple(dict(item) for item in self._scan_ruleset_list_items)
        )

    def get_scan_rule_set(self, name: str) -> dict[str, Any]:
        self.get_scan_ruleset_calls.append(name)
        if name not in self._scan_ruleset_get_bodies:
            msg = f"missing fixture for get_scan_rule_set({name!r})"
            raise KeyError(msg)
        return dict(self._scan_ruleset_get_bodies[name])
