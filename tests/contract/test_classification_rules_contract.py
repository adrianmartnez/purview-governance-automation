"""API contract tests for Classification Rules LIST/GET."""

from __future__ import annotations

import pytest

from purview_governance.remote_state.errors import RemoteStateError
from purview_governance.remote_state.service import capture_remote_state_v2
from purview_governance.scanning import (
    SCANNING_API_VERSION,
    PurviewHttpError,
    PurviewPaginationError,
)
from tests.contract.client_helpers import make_loopback_client
from tests.contract.server import (
    AUTH_SENTINEL,
    custom_classification_rule_fixture,
    start_contract_server,
)

AUTH_RAW = AUTH_SENTINEL


@pytest.mark.api_contract
def test_list_classification_rules_empty_and_success() -> None:
    with start_contract_server(classification_rule_list_mode="empty") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_classification_rules()
        assert result.item_count == 0
        rec = server.state.recordings[0]
        assert rec.path == "/scan/classificationrules"
        assert rec.api_version == SCANNING_API_VERSION

    with start_contract_server(classification_rule_list_mode="success") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_classification_rules()
        assert result.item_count == 1
        assert result.items[0]["name"] == "CustomRuleOne"


@pytest.mark.api_contract
def test_get_classification_rule_success_and_not_found() -> None:
    body = custom_classification_rule_fixture("CustomRuleOne")
    with start_contract_server(classification_rule_bodies={"CustomRuleOne": body}) as server:
        with make_loopback_client(server.base_url) as client:
            data = client.get_classification_rule("CustomRuleOne")
        assert data["kind"] == "Custom"
        assert data["properties"]["classificationAction"] == "Keep"
        assert data["properties"]["version"] == 4

    with (
        start_contract_server(classification_rule_get_mode="not_found") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewHttpError) as exc,
    ):
        client.get_classification_rule("missing-rule")
    assert exc.value.status_code == 404
    assert AUTH_RAW not in str(exc.value)


@pytest.mark.api_contract
def test_list_paginated_classification_rules() -> None:
    with start_contract_server(classification_rule_list_mode="paginated") as server:
        with make_loopback_client(server.base_url) as client:
            result = client.list_classification_rules()
        assert [item["name"] for item in result.items] == ["RuleOne", "RuleTwo"]
        assert len(server.state.recordings) == 2


@pytest.mark.api_contract
def test_cross_origin_next_link_rejected() -> None:
    with (
        start_contract_server(classification_rule_list_mode="cross_origin") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewPaginationError),
    ):
        client.list_classification_rules()
    assert len(server.state.recordings) == 1


@pytest.mark.api_contract
def test_loop_next_link_rejected() -> None:
    with (
        start_contract_server(classification_rule_list_mode="loop_next") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewPaginationError),
    ):
        client.list_classification_rules()


@pytest.mark.api_contract
def test_page_limit_exceeded() -> None:
    with (
        start_contract_server(classification_rule_list_mode="page_limit") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(PurviewPaginationError) as exc,
    ):
        client.list_classification_rules()
    assert exc.value.code == "scanning.pagination_limit_exceeded"


@pytest.mark.api_contract
def test_capture_mixed_custom_and_system() -> None:
    custom = custom_classification_rule_fixture("CustomRuleOne")
    with start_contract_server(
        classification_rule_list_mode="mixed",
        classification_rule_bodies={"CustomRuleOne": custom},
    ) as server:
        with make_loopback_client(server.base_url) as client:
            state = capture_remote_state_v2(client)
        assert len(state.classification_rules) == 1
        assert state.classification_rules[0].name == "CustomRuleOne"
        assert len(state.uninterpreted_classification_rules) == 1
        assert state.uninterpreted_classification_rules[0].kind == "System"
        # System should not trigger a GET
        get_paths = [
            r.path
            for r in server.state.recordings
            if r.path.startswith("/scan/classificationrules/")
        ]
        assert get_paths == ["/scan/classificationrules/CustomRuleOne"]


@pytest.mark.api_contract
def test_duplicate_name_across_pages_fail_closed() -> None:
    with (
        start_contract_server(classification_rule_list_mode="duplicate_cross_page") as server,
        make_loopback_client(server.base_url) as client,
        pytest.raises(RemoteStateError) as exc,
    ):
        capture_remote_state_v2(client)
    assert exc.value.code == "remote_state.duplicate_name"
