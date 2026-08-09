"""Packaged remote-state schema load smoke."""

from __future__ import annotations

from purview_governance.remote_state import load_remote_state_v1_schema


def test_remote_state_schema_packaged() -> None:
    schema = load_remote_state_v1_schema()
    assert schema["$id"].endswith("/purview-remote-state/v1")
    assert schema["properties"]["apiVersion"]["const"] == "purview-remote-state/v1"
