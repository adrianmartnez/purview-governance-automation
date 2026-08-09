"""Contract-lane readiness: local HTTP fixture starts, answers, and tears down."""

from __future__ import annotations

import json
import urllib.request

import pytest

from tests.contract.harness import HEALTH_PAYLOAD, start_local_harness


@pytest.mark.api_contract
def test_local_harness_health_round_trip() -> None:
    with (
        start_local_harness() as harness,
        urllib.request.urlopen(harness.health_url, timeout=2) as response,
    ):
        assert response.status == 200
        payload = json.loads(response.read().decode("utf-8"))
    assert payload == HEALTH_PAYLOAD
    assert harness.host == "127.0.0.1"
