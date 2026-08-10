"""Builder outcome matrix and summary tests."""

from __future__ import annotations

from purview_governance.config.models import (
    AuthenticationConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    TargetConfig,
)
from purview_governance.plan import build_governance_plan, format_plan_summary
from purview_governance.remote_state.models import UninterpretedDataSource, build_remote_state
from tests.plan.helpers import create_config, empty_config, empty_remote, remote_ds


def test_empty_plan_ready() -> None:
    plan = build_governance_plan(empty_config(), empty_remote())
    assert plan.execution_eligibility == "ready"
    assert plan.summary.total == 0
    assert plan.operations == ()


def test_create_operation_ready() -> None:
    plan = build_governance_plan(create_config(), empty_remote())
    assert plan.execution_eligibility == "ready"
    assert plan.summary.create == 1
    assert len(plan.operations) == 1
    assert plan.operations[0].action == "create"
    assert plan.operations[0].sequence == 1


def test_replace_operation_ready() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    plan = build_governance_plan(create_config(), remote)
    assert plan.execution_eligibility == "ready"
    assert plan.summary.replace == 1
    assert plan.operations[0].action == "replace"
    assert plan.desired_state.data_sources[0].endpoint == "https://example.blob.core.windows.net/"


def test_noop_zero_operations() -> None:
    remote = build_remote_state((remote_ds(),), ())
    plan = build_governance_plan(create_config(), remote)
    assert plan.execution_eligibility == "ready"
    assert plan.summary.no_op == 1
    assert plan.operations == ()


def test_remote_only_zero_operations() -> None:
    remote = build_remote_state((remote_ds(name="unmanaged"),), ())
    plan = build_governance_plan(empty_config(), remote)
    assert plan.execution_eligibility == "ready"
    assert plan.summary.remote_only == 1
    assert plan.operations == ()


def test_blocked_zero_ops_for_item() -> None:
    remote = build_remote_state((remote_ds(creation_type="AutoNative"),), ())
    plan = build_governance_plan(create_config(), remote)
    assert plan.execution_eligibility == "blocked"
    assert plan.summary.blocked == 1
    assert plan.operations == ()


def test_mixed_create_and_blocked_eligibility_blocked() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(
            DataSourceResourceConfig(
                name="alpha-source",
                kind="AzureStorage",
                endpoint="https://alpha.blob.core.windows.net/",
                collection_reference_name="root",
            ),
            DataSourceResourceConfig(
                name="beta-source",
                kind="AzureStorage",
                endpoint="https://beta.blob.core.windows.net/",
                collection_reference_name="root",
            ),
        ),
    )
    remote = build_remote_state((remote_ds(name="beta-source", creation_type="AutoManaged"),), ())
    plan = build_governance_plan(config, remote)
    assert plan.execution_eligibility == "blocked"
    assert plan.summary.create == 1
    assert plan.summary.blocked == 1
    assert len(plan.operations) == 1
    assert plan.operations[0].name == "alpha-source"
    text = format_plan_summary(plan)
    assert "executionEligibility: blocked" in text
    assert "ZERO WRITES" in text


def test_create_replace_deterministic_order() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(
            DataSourceResourceConfig(
                name="zeta-source",
                kind="AzureStorage",
                endpoint="https://zeta.blob.core.windows.net/",
                collection_reference_name="root",
            ),
            DataSourceResourceConfig(
                name="alpha-source",
                kind="AzureStorage",
                endpoint="https://alpha.blob.core.windows.net/",
                collection_reference_name="root",
            ),
        ),
    )
    remote = build_remote_state(
        (remote_ds(name="zeta-source", endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    plan = build_governance_plan(config, remote)
    assert [op.name for op in plan.operations] == ["alpha-source", "zeta-source"]
    assert [op.action for op in plan.operations] == ["create", "replace"]
    assert [op.sequence for op in plan.operations] == [1, 2]


def test_unsupported_remote_blocked() -> None:
    remote = build_remote_state(
        (),
        (
            UninterpretedDataSource(
                name="weird-source",
                kind="AdlsGen2",
                reason_code="remote_state.unsupported_kind",
            ),
        ),
    )
    plan = build_governance_plan(empty_config(), remote)
    assert plan.execution_eligibility == "blocked"
    assert plan.summary.blocked == 1
