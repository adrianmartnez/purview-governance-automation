"""Read-model coverage serialization tests."""

from __future__ import annotations

from purview_governance.remote_state.models_v3 import ReadModelCoverageV3


def test_read_model_coverage_sparse_positive_only() -> None:
    coverage = ReadModelCoverageV3(
        data_assets=True,
        relationship_data_product_to_data_asset=True,
    )
    doc = coverage.to_document()
    assert doc == {
        "dataAssets": True,
        "governanceRelationships": {"dataProductToDataAsset": True},
    }
    assert "dataColumns" not in doc
    assert "false" not in str(doc)
