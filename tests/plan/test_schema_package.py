"""Packaged governance-plan schema load smoke."""

from __future__ import annotations

from purview_governance.plan import load_plan_v1_schema, load_plan_v2_schema, load_plan_v3_schema


def test_plan_schema_packaged() -> None:
    schema = load_plan_v1_schema()
    assert schema["$id"].endswith("/purview-governance-plan/v1")
    assert schema["properties"]["apiVersion"]["const"] == "purview-governance-plan/v1"


def test_plan_v2_schema_packaged() -> None:
    schema = load_plan_v2_schema()
    assert schema["$id"].endswith("/purview-governance-plan/v2")
    assert schema["properties"]["apiVersion"]["const"] == "purview-governance-plan/v2"
    required = set(schema["properties"]["desiredState"]["required"])
    assert {
        "dataSources",
        "classificationRules",
        "scanRuleSets",
        "scans",
    }.issubset(required)
    type_enum = schema["properties"]["changeSet"]["properties"]["items"]["items"]["properties"][
        "type"
    ]["enum"]
    assert "classificationRule" in type_enum
    op_enum = schema["properties"]["operations"]["items"]["properties"]["type"]["enum"]
    assert "classificationRule" in op_enum


def test_plan_v3_schema_packaged() -> None:
    schema = load_plan_v3_schema()
    assert schema["$id"].endswith("/purview-governance-plan/v3")
    assert schema["properties"]["apiVersion"]["const"] == "purview-governance-plan/v3"
    assert (
        schema["properties"]["configurationApiVersion"]["const"] == "purview-governance-config/v3"
    )
    assert "tenantId" in schema["properties"]["targetContext"]["properties"]
