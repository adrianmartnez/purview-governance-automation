"""Tests for config -> desired-state mapping."""

from __future__ import annotations

from purview_governance.config import validate_config_text
from purview_governance.desired import desired_state_from_config

CONFIG = """
apiVersion: purview-governance-config/v1
target:
  endpoint: https://contoso-fictional.purview.azure.com
authentication:
  strategy: defaultAzureCredential
resources:
  - type: dataSource
    name: zetaSource
    kind: AzureStorage
    properties:
      endpoint: https://zeta.blob.core.windows.net/
      collection:
        referenceName: root
  - type: dataSource
    name: alphaSource
    kind: AzureStorage
    properties:
      endpoint: https://alpha.blob.core.windows.net/
      collection:
        referenceName: Collection-rZX
"""


def test_mapping_orders_by_name_and_is_pure() -> None:
    config = validate_config_text(CONFIG, format_hint="yaml")
    desired = desired_state_from_config(config)
    assert [item.name for item in desired.data_sources] == ["alphaSource", "zetaSource"]
    assert desired.data_sources[0].endpoint == "https://alpha.blob.core.windows.net/"
    assert desired.data_sources[0].collection_reference_name == "Collection-rZX"
