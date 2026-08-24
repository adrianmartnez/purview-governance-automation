"""Read-model coverage markers for PR5 remote-state/v3 extensions."""

from __future__ import annotations

READ_MODEL_COVERAGE_DATA_ASSETS = "dataAssets"
READ_MODEL_COVERAGE_DATA_COLUMNS = "dataColumns"
READ_MODEL_COVERAGE_GOVERNANCE_RELATIONSHIPS = "governanceRelationships"

RELATIONSHIP_FAMILY_DATA_PRODUCT_TO_DATA_ASSET = "dataProductToDataAsset"
RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_ASSET = "glossaryTermToDataAsset"
RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_COLUMN = "glossaryTermToDataColumn"

RELATIONSHIP_FAMILIES: frozenset[str] = frozenset(
    {
        RELATIONSHIP_FAMILY_DATA_PRODUCT_TO_DATA_ASSET,
        RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_ASSET,
        RELATIONSHIP_FAMILY_GLOSSARY_TERM_TO_DATA_COLUMN,
    }
)

GOVERNANCE_RELATIONSHIP_TARGET_CATEGORIES: frozenset[str] = frozenset({"DATAASSET", "DATACOLUMN"})

GOVERNANCE_RELATIONSHIP_SOURCE_TYPES: frozenset[str] = frozenset({"dataProduct", "glossaryTerm"})

APPROVED_RELATIONSHIP_TYPES: frozenset[str] = frozenset({"Related"})
