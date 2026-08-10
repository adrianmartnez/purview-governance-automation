"""Secret-sentinel sanitization for plan loader/builder errors."""

from __future__ import annotations

import json
import traceback

import pytest

from purview_governance.plan import (
    PlanBuildError,
    PlanIntegrityError,
    PlanLoadError,
    build_governance_plan,
    format_plan_summary,
    load_plan_text,
)
from purview_governance.remote_state.models import build_remote_state
from tests.plan.helpers import create_config, empty_remote, recompute_plan_identity, remote_ds

SECRET_SENTINEL = "SECRET_SENTINEL_do-not-leak-plan-material-9f3c"


def _assert_sanitized(error: BaseException) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert SECRET_SENTINEL not in str(error)
    assert SECRET_SENTINEL not in repr(error)
    assert SECRET_SENTINEL not in "".join(traceback.format_exception(error))
    assert not any(
        value is not None and SECRET_SENTINEL in str(value) for _name, value in vars(error).items()
    )


def test_malformed_json_with_sentinel_sanitized() -> None:
    with pytest.raises(PlanLoadError) as exc_info:
        load_plan_text("{ not-json " + SECRET_SENTINEL)
    _assert_sanitized(exc_info.value)


def test_unsafe_endpoint_reason_before_sanitized() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"][0]["before"] = (
        f"https://x.blob.core.windows.net/?sig={SECRET_SENTINEL}"
    )
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    _assert_sanitized(exc_info.value)


def test_unsafe_endpoint_reason_after_userinfo_sanitized() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"][0]["after"] = (
        f"https://{SECRET_SENTINEL}:pw@example.blob.core.windows.net/"
    )
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    _assert_sanitized(exc_info.value)


def test_fragment_endpoint_reason_sanitized() -> None:
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"][0]["after"] = (
        f"https://example.blob.core.windows.net/#{SECRET_SENTINEL}"
    )
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError) as exc_info:
        load_plan_text(json.dumps(document))
    _assert_sanitized(exc_info.value)


def test_format_plan_summary_never_sees_unsafe_loaded_plan() -> None:
    # Only loaded/built plans reach summary; unsafe plans fail load first.
    remote = build_remote_state(
        (remote_ds(endpoint="https://old.blob.core.windows.net/"),),
        (),
    )
    document = build_governance_plan(create_config(), remote).to_document()
    document["changeSet"]["items"][0]["reasons"][0]["before"] = (
        f"https://x.blob.core.windows.net/?sig={SECRET_SENTINEL}"
    )
    document = recompute_plan_identity(document)
    with pytest.raises(PlanIntegrityError):
        plan = load_plan_text(json.dumps(document))
        format_plan_summary(plan)


def test_manual_invalid_config_error_sanitized() -> None:
    from purview_governance.config.models import (
        AuthenticationConfig,
        DataSourceResourceConfig,
        GovernanceConfig,
        TargetConfig,
    )

    config = GovernanceConfig(
        api_version="purview-governance-config/v1",
        target=TargetConfig(endpoint="https://account.purview.azure.com"),
        authentication=AuthenticationConfig(strategy="defaultAzureCredential"),
        resources=(
            DataSourceResourceConfig(
                name="example-source",
                kind="BogusKind",
                endpoint=f"https://example.blob.core.windows.net/{SECRET_SENTINEL}",
                collection_reference_name="root",
            ),
        ),
    )
    # BogusKind fails schema before endpoint path matters; ensure sanitized either way.
    with pytest.raises(PlanBuildError) as exc_info:
        build_governance_plan(config, empty_remote())
    _assert_sanitized(exc_info.value)
