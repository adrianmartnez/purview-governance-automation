"""Offline CLI reviewer workflow for Unified Catalog config/plan/apply v3."""

from __future__ import annotations

import contextlib
import json
from io import StringIO
from pathlib import Path

from purview_governance.apply import RESULT_API_VERSION_V3, load_execution_result_file
from purview_governance.auth.provider import PurviewAuthorizationProvider
from purview_governance.auth.tenant_bound import TenantBoundAuthorizationProvider
from purview_governance.cli import EXIT_SUCCESS, _CliDependencies, _run
from purview_governance.config.models_v3 import CONFIG_API_VERSION_V3
from purview_governance.plan import PLAN_API_VERSION_V3, load_plan_v3_file
from purview_governance.remote_state import REMOTE_STATE_API_VERSION_V3
from purview_governance.unified_catalog.client import PurviewUnifiedCatalogClient
from purview_governance.unified_catalog.constants import (
    BUSINESS_DOMAINS_PATH,
    DATA_PRODUCTS_PATH,
    GLOSSARY_TERMS_PATH,
)
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    DOMAIN_B,
    OWNER_ID,
    PRODUCT_A,
    TENANT_ID,
    TERM_CHILD,
    TERM_PARENT,
)
from tests.auth.tenant_bound_fakes import OfflineClientSecretCredential
from tests.contract.auth import AUTH_SENTINEL
from tests.contract.unified_catalog_server import (
    fictional_business_domain_item,
    fictional_data_product_item,
    start_unified_catalog_contract_server,
)

_DESIRED_DESCRIPTION = "desired-product-description"
_DRIFTED_DESCRIPTION = "drifted-product-description"


def _offline_config_yaml() -> str:
    return f"""
apiVersion: {CONFIG_API_VERSION_V3}
target:
  surface: unifiedCatalog
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
      status: PUBLISHED
      type: FunctionalUnit
      parentId: {DOMAIN_A}
  - type: dataProduct
    id: {PRODUCT_A}
    properties:
      name: sales-product
      domain: {DOMAIN_A}
      type: Master
      description: {_DESIRED_DESCRIPTION}
      businessUse: Primary business use
      owners:
        - id: {OWNER_ID}
  - type: glossaryTerm
    id: {TERM_PARENT}
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: {OWNER_ID}
  - type: glossaryTerm
    id: {TERM_CHILD}
    properties:
      name: child-term
      domain: {DOMAIN_A}
      description: Child term
      owners:
        - id: {OWNER_ID}
      parentId: {TERM_PARENT}
"""


def _seed_domains() -> list[dict]:
    root = fictional_business_domain_item(domain_id=DOMAIN_A, name="root-domain")
    root["type"] = "DataDomain"
    child = fictional_business_domain_item(domain_id=DOMAIN_B, name="child-domain")
    child["type"] = "FunctionalUnit"
    child["parentId"] = DOMAIN_A
    return [root, child]


def _seed_product() -> dict:
    product = fictional_data_product_item(
        product_id=PRODUCT_A,
        name="sales-product",
        domain_id=DOMAIN_A,
        product_type="Master",
        owner_id=OWNER_ID,
    )
    product["description"] = _DRIFTED_DESCRIPTION
    product["businessUse"] = "Primary business use"
    product["status"] = "DRAFT"
    return product


def _make_deps(server) -> _CliDependencies:
    token = AUTH_SENTINEL.removeprefix("Bearer ").strip()

    def credential_provider_factory(
        selector: str | None,
        *,
        tenant_id: str,
        endpoint: str | None = None,
        tenant_bound: bool = False,
    ):
        del selector
        credential = OfflineClientSecretCredential(token=token)
        if tenant_bound:
            assert endpoint is not None
            return TenantBoundAuthorizationProvider(
                credential,
                tenant_id=tenant_id,
                endpoint=endpoint,
            )
        return PurviewAuthorizationProvider(credential)

    def uc_factory(endpoint: str, provider):
        return PurviewUnifiedCatalogClient._from_loopback_base_url(
            server.base_url,
            provider,
            logical_target_endpoint=endpoint,
        )

    return _CliDependencies(
        unified_catalog_client_factory=uc_factory,
        credential_provider_factory=credential_provider_factory,
    )


def test_offline_v3_workflow(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg-v3.yaml"
    config_path.write_text(_offline_config_yaml(), encoding="utf-8")
    remote_audit_path = tmp_path / "remote-audit.json"
    plan_remote_path = tmp_path / "plan-remote.json"
    plan_path = tmp_path / "plan.json"
    dry_result_path = tmp_path / "dry-result.json"
    result_path = tmp_path / "result.json"
    replan_remote_path = tmp_path / "replan-remote.json"
    replan_path = tmp_path / "replan.json"
    noop_result_path = tmp_path / "noop-result.json"

    with start_unified_catalog_contract_server(
        enumerate_items=_seed_domains(),
        enumerate_data_products_items=[_seed_product()],
        enumerate_glossary_terms_items=[],
    ) as server:
        deps = _make_deps(server)

        validate_buf = StringIO()
        with contextlib.redirect_stdout(validate_buf):
            assert (
                _run(["config", "validate", str(config_path), "--json"], deps=deps) == EXIT_SUCCESS
            )
        validate_doc = json.loads(validate_buf.getvalue())
        assert validate_doc["status"] == "valid"
        assert validate_doc["apiVersion"] == CONFIG_API_VERSION_V3

        assert (
            _run(
                [
                    "remote-state",
                    "capture",
                    str(config_path),
                    "--output",
                    str(remote_audit_path),
                    "--credential",
                    "azure-cli",
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        remote_doc = json.loads(remote_audit_path.read_text(encoding="utf-8"))
        assert remote_doc["apiVersion"] == REMOTE_STATE_API_VERSION_V3
        assert len(remote_doc["businessDomains"]) == 2
        assert len(remote_doc["dataProducts"]) == 1
        assert remote_doc["glossaryTerms"] == []

        assert (
            _run(
                [
                    "plan",
                    "create",
                    str(config_path),
                    "--output",
                    str(plan_path),
                    "--remote-state-output",
                    str(plan_remote_path),
                    "--credential",
                    "azure-cli",
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        plan = load_plan_v3_file(plan_path)
        assert plan.api_version == PLAN_API_VERSION_V3
        assert plan.execution_eligibility == "ready"
        assert plan.summary.create == 2
        assert plan.summary.replace == 1
        assert {op.resource_type for op in plan.operations} == {
            "dataProduct",
            "glossaryTerm",
        }

        assert _run(["plan", "inspect", str(plan_path)], deps=deps) == EXIT_SUCCESS

        assert (
            _run(
                [
                    "apply",
                    str(plan_path),
                    "--remote-state",
                    str(plan_remote_path),
                    "--credential",
                    "azure-cli",
                    "--result",
                    str(dry_result_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        dry = load_execution_result_file(dry_result_path)
        assert dry.api_version == RESULT_API_VERSION_V3
        assert dry.status == "dry-run-ready"
        assert dry.writes_attempted == 0
        assert not any(r.method in {"POST", "PUT", "DELETE"} for r in server.state.recordings)

        assert (
            _run(
                [
                    "apply",
                    str(plan_path),
                    "--apply",
                    "--remote-state",
                    str(plan_remote_path),
                    "--credential",
                    "azure-cli",
                    "--result",
                    str(result_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        applied = load_execution_result_file(result_path)
        assert applied.api_version == RESULT_API_VERSION_V3
        assert applied.status == "applied"
        assert applied.writes_performed == 3
        assert applied.writes_attempted == 3

        mutating = [r for r in server.state.recordings if r.method in {"POST", "PUT", "DELETE"}]
        assert [(r.method, r.path) for r in mutating] == [
            ("PUT", f"{DATA_PRODUCTS_PATH}/{PRODUCT_A}"),
            ("POST", GLOSSARY_TERMS_PATH),
            ("POST", GLOSSARY_TERMS_PATH),
        ]
        assert mutating[1].json_body is not None
        assert mutating[1].json_body.get("id") == TERM_PARENT
        assert mutating[2].json_body is not None
        assert mutating[2].json_body.get("id") == TERM_CHILD
        assert not any(r.method == "POST" and r.path == BUSINESS_DOMAINS_PATH for r in mutating)
        assert not any(r.method == "DELETE" for r in mutating)

        assert _run(["result", "inspect", str(result_path)], deps=deps) == EXIT_SUCCESS

        assert (
            _run(
                [
                    "plan",
                    "create",
                    str(config_path),
                    "--output",
                    str(replan_path),
                    "--remote-state-output",
                    str(replan_remote_path),
                    "--credential",
                    "azure-cli",
                    "--force",
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        replan = load_plan_v3_file(replan_path)
        assert replan.api_version == PLAN_API_VERSION_V3
        assert replan.operations == ()
        assert replan.summary.create == 0
        assert replan.summary.replace == 0

        assert (
            _run(
                [
                    "apply",
                    str(replan_path),
                    "--apply",
                    "--remote-state",
                    str(replan_remote_path),
                    "--credential",
                    "azure-cli",
                    "--result",
                    str(noop_result_path),
                ],
                deps=deps,
            )
            == EXIT_SUCCESS
        )
        noop = load_execution_result_file(noop_result_path)
        assert noop.status == "applied"
        assert noop.writes_attempted == 0
        mutating_after = [
            r for r in server.state.recordings if r.method in {"POST", "PUT", "DELETE"}
        ]
        assert len(mutating_after) == 3
