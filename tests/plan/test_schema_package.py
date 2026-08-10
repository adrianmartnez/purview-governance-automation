"""Packaged governance-plan schema load smoke."""

from __future__ import annotations

from purview_governance.plan import load_plan_v1_schema, load_plan_v2_schema


def test_plan_schema_packaged() -> None:
    schema = load_plan_v1_schema()
    assert schema["$id"].endswith("/purview-governance-plan/v1")
    assert schema["properties"]["apiVersion"]["const"] == "purview-governance-plan/v1"


def test_plan_v2_schema_packaged() -> None:
    schema = load_plan_v2_schema()
    assert schema["$id"].endswith("/purview-governance-plan/v2")
    assert schema["properties"]["apiVersion"]["const"] == "purview-governance-plan/v2"
