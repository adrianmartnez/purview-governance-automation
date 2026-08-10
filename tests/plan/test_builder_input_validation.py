"""Builder rejects untrusted manual GovernanceConfig / RemoteState inputs."""

from __future__ import annotations

import pytest

from purview_governance.config.models import (
    AuthenticationConfig,
    DataSourceResourceConfig,
    GovernanceConfig,
    TargetConfig,
)
from purview_governance.plan import PlanBuildError, build_governance_plan
from purview_governance.remote_state.canonical import compute_material_state_identity
from purview_governance.remote_state.models import (
    RemoteState,
    UninterpretedDataSource,
    build_remote_state,
)
from tests.plan.helpers import create_config, empty_remote, remote_ds


def test_wrong_api_version_rejected() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v999",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(),
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(config, empty_remote())
    assert exc_info.value.code == "plan.invalid_configuration_input"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_wrong_auth_strategy_rejected() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="clientSecret"),
        resources=(),
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(config, empty_remote())
    assert exc_info.value.code == "plan.invalid_configuration_input"


def test_bogus_kind_never_reinterpreted() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(
            DataSourceResourceConfig(
                name="example-source",
                kind="BogusKind",
                endpoint="https://example.blob.core.windows.net/",
                collection_reference_name="root",
            ),
        ),
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(config, empty_remote())
    assert exc_info.value.code == "plan.invalid_configuration_input"


def test_invalid_name_rejected() -> None:
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(
            DataSourceResourceConfig(
                name="ab",
                kind="AzureStorage",
                endpoint="https://example.blob.core.windows.net/",
                collection_reference_name="root",
            ),
        ),
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(config, empty_remote())
    assert exc_info.value.code == "plan.invalid_configuration_input"


def test_duplicate_names_rejected() -> None:
    resource = DataSourceResourceConfig(
        name="example-source",
        kind="AzureStorage",
        endpoint="https://example.blob.core.windows.net/",
        collection_reference_name="root",
    )
    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(resource, resource),
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(config, empty_remote())
    assert exc_info.value.code == "plan.invalid_configuration_input"


def test_blank_and_whitespace_collection_ref_rejected() -> None:
    for ref in ("", "   ", "  Collection-X  "):
        config = GovernanceConfig(
            api_version="purview-governance-config/v1",
            target=TargetConfig(endpoint="https://account.purview.azure.com"),
            authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
            resources=(
                DataSourceResourceConfig(
                    name="example-source",
                    kind="AzureStorage",
                    endpoint="https://example.blob.core.windows.net/",
                    collection_reference_name=ref,
                ),
            ),
        )
        with pytest.raises(PlanBuildError) as exc_info:
            build_governance_plan(config, empty_remote())
        assert exc_info.value.code == "plan.invalid_configuration_input"


def test_duplicate_supported_remote_rejected() -> None:
    item = remote_ds()
    # Bypass build_remote_state sorting/uniqueness by constructing RemoteState directly
    # with a recomputed matching identity for the (invalid) document.
    provisional = RemoteState(
        data_sources=(item, item),
        uninterpreted_data_sources=(),
        material_state_identity="",
    )
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState(
        data_sources=(item, item),
        uninterpreted_data_sources=(),
        material_state_identity=identity,
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_duplicate_uninterpreted_rejected() -> None:
    item = UninterpretedDataSource(
        name="weird-source",
        kind="AdlsGen2",
        reason_code="remote_state.unsupported_kind",
    )
    provisional = RemoteState((), (item, item), "")
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState((), (item, item), identity)
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_overlap_supported_uninterpreted_rejected() -> None:
    supported = remote_ds(name="shared-name")
    uninterpreted = UninterpretedDataSource(
        name="shared-name",
        kind="AdlsGen2",
        reason_code="remote_state.unsupported_kind",
    )
    provisional = RemoteState((supported,), (uninterpreted,), "")
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState((supported,), (uninterpreted,), identity)
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_unsorted_hash_consistent_remote_rejected() -> None:
    a = remote_ds(name="alpha-source")
    z = remote_ds(name="zeta-source")
    provisional = RemoteState((z, a), (), "")
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState((z, a), (), identity)
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_arbitrary_uninterpreted_reason_code_rejected() -> None:
    item = UninterpretedDataSource(
        name="weird-source",
        kind="AdlsGen2",
        reason_code="remote_state.custom_reason",
    )
    provisional = RemoteState((), (item,), "")
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState((), (item,), identity)
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_uninterpreted_azurestorage_kind_rejected() -> None:
    item = UninterpretedDataSource(
        name="x-source",
        kind="AzureStorage",
        reason_code="remote_state.unsupported_kind",
    )
    provisional = RemoteState((), (item,), "")
    identity = compute_material_state_identity(provisional.identity_document())
    remote = RemoteState((), (item,), identity)
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.invalid_remote_state_input"


def test_inconsistent_remote_identity_rejected() -> None:
    item = remote_ds()
    remote = RemoteState(
        data_sources=(item,),
        uninterpreted_data_sources=(),
        material_state_identity="sha256:" + ("0" * 64),
    )
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(create_config(), remote)
    assert exc_info.value.code == "plan.inconsistent_remote_identity"


def test_valid_build_remote_state_accepted() -> None:
    remote = build_remote_state((remote_ds(),), ())
    plan = build_governance_plan(create_config(), remote)
    assert plan.summary.no_op == 1
