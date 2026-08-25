"""PR6 regression: PlanBuildError from remote validation maps to invalid_remote_state."""

from __future__ import annotations

import pytest

from purview_governance.apply import ExecutionMode, execute_governance_plan_v3
from tests.apply.helpers_v3 import (
    DOMAIN_A,
    OWNER_ID,
    TERM_PARENT,
    apply_server,
    base_config_header,
    build_plan_from_yaml,
    capture_remote_for_apply,
    make_tenant_bound_client,
)


def _ready_term_yaml() -> str:
    return (
        base_config_header()
        + f"""
  - type: glossaryTerm
    id: {TERM_PARENT}
    properties:
      name: parent-term
      domain: {DOMAIN_A}
      description: Parent term
      owners:
        - id: {OWNER_ID}
"""
    )


def test_planbuilderror_from_invalid_remote_fails_before_write() -> None:
    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(_ready_term_yaml(), remote)
            assert plan.execution_eligibility == "ready"

            object.__setattr__(
                remote,
                "material_state_identity",
                "sha256:" + ("f" * 64),
            )
            before = len(server.state.recordings)
            result = execute_governance_plan_v3(
                plan,
                remote,
                client,
                mode=ExecutionMode.APPLY,
            )
            mutating = [
                r for r in server.state.recordings[before:] if r.method in {"POST", "PUT", "DELETE"}
            ]
        finally:
            client.close()

    assert result.status == "failed-before-write"
    assert result.failure is not None
    assert result.failure.code == "apply.invalid_remote_state"
    assert result.writes_attempted == 0
    assert result.writes_performed == 0
    assert result.writes_unknown == 0
    assert all(op.status == "not-run" for op in result.operations)
    assert mutating == []


def test_unexpected_exception_not_misclassified_as_invalid_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_remote: object) -> None:
        raise RuntimeError("unexpected-validator-failure")

    monkeypatch.setattr(
        "purview_governance.apply.service_v3.validate_remote_state_for_planning_v3",
        _boom,
    )

    with apply_server() as server:
        client = make_tenant_bound_client(server.base_url)
        try:
            remote = capture_remote_for_apply(client, include_glossary_terms=True)
            plan = build_plan_from_yaml(_ready_term_yaml(), remote)
            assert plan.execution_eligibility == "ready"
            with pytest.raises(RuntimeError, match="unexpected-validator-failure"):
                execute_governance_plan_v3(
                    plan,
                    remote,
                    client,
                    mode=ExecutionMode.DRY_RUN,
                )
        finally:
            client.close()
