"""Tests for governance config v3 Glossary Terms."""

from __future__ import annotations

import pytest

from purview_governance.config.diagnostics import ConfigValidationError
from purview_governance.config.models_v3 import CONFIG_API_VERSION_V3, UNIFIED_CATALOG_SURFACE
from purview_governance.config.service_v3 import validate_config_v3_text
from purview_governance.desired.mapping_v3 import desired_state_from_config_v3

TENANT_ID = "20000000-0000-4000-8000-000000000001"
DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
OWNER_A = "30000000-0000-4000-8000-000000000001"
GT_ROOT = "50000000-0000-4000-8000-000000000001"
GT_CHILD = "50000000-0000-4000-8000-000000000002"


def _config_header() -> str:
    return f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: {UNIFIED_CATALOG_SURFACE}
  tenantId: {TENANT_ID}
authentication:
  strategy: defaultAzureCredential
resources:
"""


def _business_domain_block(domain_id: str = DOMAIN_A) -> str:
    return f"""
  - type: businessDomain
    id: {domain_id}
    properties:
      name: root-domain
      status: PUBLISHED
      type: DataDomain
"""


def _glossary_term_block(
    *,
    term_id: str = GT_ROOT,
    name: str = "revenue",
    domain: str = DOMAIN_A,
    parent_id: str | None = None,
    acronyms_yaml: str = "",
) -> str:
    parent_line = f"\n      parentId: {parent_id}" if parent_id else ""
    return f"""
  - type: glossaryTerm
    id: {term_id}
    properties:
      name: {name}
      domain: {domain}
      description: Term description
      owners:
        - id: {OWNER_A}{parent_line}{acronyms_yaml}
"""


def test_validate_v3_glossary_term_accepts_root_term() -> None:
    yaml = _config_header() + _business_domain_block() + _glossary_term_block()
    config = validate_config_v3_text(yaml, format_hint="yaml")
    assert len(config.glossary_terms) == 1
    assert config.glossary_terms[0].parent_id is None
    assert config.glossary_terms[0].acronyms is None


def test_validate_v3_glossary_term_rejects_duplicate_id() -> None:
    yaml = (
        _config_header()
        + _business_domain_block()
        + _glossary_term_block(term_id=GT_ROOT, name="term-a")
        + _glossary_term_block(term_id=GT_ROOT, name="term-b")
    )
    with pytest.raises(ConfigValidationError, match="duplicate_glossary_term_id"):
        validate_config_v3_text(yaml, format_hint="yaml")


def test_validate_v3_glossary_term_rejects_self_parent() -> None:
    yaml = _config_header() + _business_domain_block() + _glossary_term_block(parent_id=GT_ROOT)
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_v3_text(yaml, format_hint="yaml")
    codes = {item.code for item in exc.value.diagnostics}
    assert "config.self_parent" in codes


def test_validate_v3_glossary_term_rejects_cycle() -> None:
    yaml = (
        _config_header()
        + _business_domain_block()
        + _glossary_term_block(term_id=GT_ROOT, parent_id=GT_CHILD)
        + _glossary_term_block(term_id=GT_CHILD, parent_id=GT_ROOT)
    )
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_v3_text(yaml, format_hint="yaml")
    codes = {item.code for item in exc.value.diagnostics}
    assert "config.hierarchy_cycle" in codes


def test_validate_v3_glossary_term_rejects_cross_domain_parent() -> None:
    yaml = (
        _config_header()
        + _business_domain_block(DOMAIN_A)
        + f"""
  - type: businessDomain
    id: {DOMAIN_B}
    properties:
      name: other-domain
      status: PUBLISHED
      type: DataDomain
"""
        + _glossary_term_block(term_id=GT_ROOT, domain=DOMAIN_A)
        + _glossary_term_block(term_id=GT_CHILD, domain=DOMAIN_B, parent_id=GT_ROOT)
    )
    with pytest.raises(ConfigValidationError, match="config.parent_domain_mismatch"):
        validate_config_v3_text(yaml, format_hint="yaml")


def test_desired_mapping_preserves_acronyms_absent_vs_empty() -> None:
    absent_yaml = (
        _config_header() + _business_domain_block() + _glossary_term_block(acronyms_yaml="")
    )
    explicit_yaml = (
        _config_header()
        + _business_domain_block()
        + _glossary_term_block(acronyms_yaml="\n      acronyms: []")
    )
    absent = desired_state_from_config_v3(validate_config_v3_text(absent_yaml, format_hint="yaml"))
    explicit = desired_state_from_config_v3(
        validate_config_v3_text(explicit_yaml, format_hint="yaml")
    )
    assert absent.glossary_terms[0].acronyms is None
    assert explicit.glossary_terms[0].acronyms == ()


def test_desired_mapping_preserves_acronyms_values() -> None:
    yaml = (
        _config_header()
        + _business_domain_block()
        + _glossary_term_block(acronyms_yaml="\n      acronyms:\n        - REV")
    )
    desired = desired_state_from_config_v3(validate_config_v3_text(yaml, format_hint="yaml"))
    assert desired.glossary_terms[0].acronyms == ("REV",)
