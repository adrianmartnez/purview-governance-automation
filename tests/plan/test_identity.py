"""Plan identity and determinism tests."""

from __future__ import annotations

from purview_governance.config.models import (
    AuthenticationConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    TargetConfig,
)
from purview_governance.plan import build_governance_plan
from purview_governance.remote_state.models import build_remote_state
from tests.plan.helpers import create_config, empty_config, empty_remote, remote_ds


def test_repeated_builds_byte_identical() -> None:
    config = create_config()
    remote = empty_remote()
    a = build_governance_plan(config, remote).to_canonical_json()
    b = build_governance_plan(config, remote).to_canonical_json()
    assert a == b
    assert a.endswith("}") and not a.endswith("}\n")


def test_resource_input_order_does_not_change_plan() -> None:
    resources_a = (
        DataSourceResourceConfig(
            name="zetaSource",
            kind="AzureStorage",
            endpoint="https://zeta.blob.core.windows.net/",
            collection_reference_name="root",
        ),
        DataSourceResourceConfig(
            name="alphaSource",
            kind="AzureStorage",
            endpoint="https://alpha.blob.core.windows.net/",
            collection_reference_name="root",
        ),
    )
    resources_b = tuple(reversed(resources_a))
    cfg_a = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=resources_a,
    )
    cfg_b = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=resources_b,
    )
    # Builder revalidates via to_document(); resources order in document follows input.
    # validate_document does not sort; normalize_document does. validate_document only
    # schemas. So different order in to_document may still be schema-valid.
    # desired_state_from_config sorts by name, so plan should match if config validates.
    plan_a = build_governance_plan(cfg_a, empty_remote())
    plan_b = build_governance_plan(cfg_b, empty_remote())
    assert plan_a.identities.desired_state == plan_b.identities.desired_state
    assert plan_a.plan_identity == plan_b.plan_identity
    assert plan_a.to_canonical_json() == plan_b.to_canonical_json()


def test_target_change_affects_target_material_plan_not_desired() -> None:
    base = create_config()
    other = GovernanceConfig(
        api_version=base.api_version,
        target=TargetConfig(endpoint="https://other.purview.azure.com"),
        authentication=base.authentication,
        resources=base.resources,
    )
    remote = empty_remote()
    plan_a = build_governance_plan(base, remote)
    plan_b = build_governance_plan(other, remote)
    assert plan_a.identities.desired_state == plan_b.identities.desired_state
    assert plan_a.target_context.identity != plan_b.target_context.identity
    assert plan_a.identities.material_configuration != plan_b.identities.material_configuration
    assert plan_a.plan_identity != plan_b.plan_identity


def test_desired_endpoint_change_affects_desired_material_plan() -> None:
    base = create_config()
    changed = GovernanceConfig(
        api_version=base.api_version,
        target=base.target,
        authentication=base.authentication,
        resources=(
            DataSourceResourceConfig(
                name="example-source",
                kind="AzureStorage",
                endpoint="https://other.blob.core.windows.net/",
                collection_reference_name="root",
            ),
        ),
    )
    remote = empty_remote()
    plan_a = build_governance_plan(base, remote)
    plan_b = build_governance_plan(changed, remote)
    assert plan_a.identities.desired_state != plan_b.identities.desired_state
    assert plan_a.identities.material_configuration != plan_b.identities.material_configuration
    assert plan_a.plan_identity != plan_b.plan_identity


def test_remote_identity_change_affects_plan() -> None:
    config = create_config()
    remote_a = empty_remote()
    remote_b = build_remote_state((remote_ds(name="remote-only"),), ())
    plan_a = build_governance_plan(config, remote_a)
    plan_b = build_governance_plan(config, remote_b)
    assert plan_a.identities.remote_state != plan_b.identities.remote_state
    assert plan_a.plan_identity != plan_b.plan_identity


def test_plan_identity_excludes_self() -> None:
    plan = build_governance_plan(empty_config(), empty_remote())
    without = plan.document_without_plan_identity()
    assert "planIdentity" not in without
    assert plan.plan_identity.startswith("sha256:")
