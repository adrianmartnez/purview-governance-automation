"""Tests for governance config v3 Business Domains."""

from __future__ import annotations

import pytest

from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.models_v3 import (
    CONFIG_API_VERSION_V3,
    UNIFIED_CATALOG_SURFACE,
)
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.desired.mapping_v3 import desired_state_from_config_v3

TENANT_ID = "20000000-0000-4000-8000-000000000001"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"

CONFIG_YAML = f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
  - type: businessDomain
    id: {DOMAIN_A}
    properties:
      name: root-domain
      status: PUBLISHED
      type: DataDomain
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: child-domain
      status: DRAFT
      type: FunctionalUnit
      parentId: {DOMAIN_A}
      description: child description
      isRestricted: true
"""


def test_validate_v3_business_domains_and_desired_mapping() -> None:
    config = validate_config_v3_text(CONFIG_YAML, format_hint="yaml")
    desired = desired_state_from_config_v3(config)

    assert len(desired.business_domains) == 2
    root = desired.business_domains[0]
    child = desired.business_domains[1]
    assert root.id == DOMAIN_A
    assert root.parent_id is None
    assert root.description is None
    assert child.parent_id == DOMAIN_A
    assert child.description == "child description"
    assert child.is_restricted is True

    doc = desired.to_document()
    assert "businessDomains" in doc
    root_doc = doc["businessDomains"][0]
    assert "description" not in root_doc["properties"]
    child_doc = doc["businessDomains"][1]
    assert child_doc["properties"]["parentId"] == DOMAIN_A
    assert child_doc["properties"]["isRestricted"] is True


def test_validate_v3_hierarchy_depth_exceeded() -> None:
    ids = [f"10000000-0000-4000-8000-{index:012x}" for index in range(1, 7)]
    resources = []
    for index, domain_id in enumerate(ids):
        props = {
            "name": f"domain-{index}",
            "status": "PUBLISHED",
            "type": "DataDomain",
        }
        if index > 0:
            props["parentId"] = ids[index - 1]
        resources.append(
            f"""  - type: businessDomain
    id: {domain_id}
    properties:
      name: {props["name"]}
      status: {props["status"]}
      type: {props["type"]}"""
            + (f"\n      parentId: {props['parentId']}" if index > 0 else "")
        )
    yaml = f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
{chr(10).join(resources)}
"""
    with pytest.raises(ConfigValidationError, match="hierarchy_depth_exceeded"):
        validate_config_v3_text(yaml, format_hint="yaml")
