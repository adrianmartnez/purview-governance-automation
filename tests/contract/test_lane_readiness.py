"""Contract-lane harness readiness tests.

These tests prove the offline api-contract-tests lane can start a deterministic
local HTTP fixture, round-trip a fixed response, and tear down cleanly.

They do not validate Microsoft Purview Scanning Data Plane contracts. The
Purview-specific mock/contract server belongs to issue #11.
"""

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
