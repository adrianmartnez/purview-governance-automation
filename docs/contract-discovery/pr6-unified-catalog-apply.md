# PR6 Contract Discovery — Unified Catalog Apply (Fase 0)

| Field | Value |
|-------|-------|
| Audit date | 2026-08-24 |
| Repository HEAD (audit) | `3d1e732cdc8d8fb4b1e70a29de76054b7283339e` |
| Package version | `1.2.0.dev0` |
| API version audited | `2026-03-20-preview` |
| Live validation | **NOT_PERFORMED** |
| Scope | Known Public Preview contract limitations / safety gates for apply/v3 |

## Primary sources

| Source | URL / path |
|--------|------------|
| Unified Catalog API overview | https://learn.microsoft.com/en-us/rest/api/purview/unified-catalog-api-overview |
| CatalogApiService.json | https://github.com/Azure/azure-rest-api-specs/blob/main/specification/purviewdatagovernance/data-plane/Azure.Analytics.Purview.UnifiedCatalog/preview/2026-03-20-preview/CatalogApiService.json |
| models.tsp | https://github.com/Azure/azure-rest-api-specs/blob/main/specification/purviewdatagovernance/data-plane/Azure.Analytics.Purview.UnifiedCatalog/models.tsp |
| Business Domain Create | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/business-domain/create?view=rest-purview-purview-unified-catalog-2026-03-20-preview |
| Terms Update | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/terms/update?view=rest-purview-purview-unified-catalog-2026-03-20-preview |

**Not used as primary proof:** project fake harness, remote normalizer, blogs, StackOverflow.

## Gate findings

```
BD_CREATE_CONTRACT=UNPROVEN
BD_PARENT_CLEAR_CONTRACT=UNPROVEN
TERM_PARENT_CLEAR_CONTRACT=UNPROVEN
```

### BD CREATE

- TypeSpec/Swagger `Domain` reuses same model for POST/PUT/response.
- Required on Create: `id`, `systemData`, `parentId`, `thumbnail`, `domains`, `managedAttributes`.
- Official `BusinessDomain_Create_Gen.json` always includes full auxiliary payload; no root CREATE without `parentId`.
- Functional UI allows optional parent; REST marks `parentId` Required — contradiction unresolved.

### BD parent clear

- `parentId` required non-nullable UUID on PUT body.
- No official omit/null/empty-UUID/unparent operation documented.
- child→root and ambiguous root→root blocked for apply/v3.

### Term parent clear

- `parentId` optional on PUT but not nullable.
- Official `Terms_Update_Gen.json` includes `parentId`; no example omitting it to clear.
- UI bulk-edit Remove is functional only, not REST wire proof.
- child→root REPLACE blocked for apply/v3.

## apply/v3 safety response

These UNPROVEN gates are **capability limitations**, not merge blockers. apply/v3:

- Does **not** implement Business Domain CREATE.
- Fail-closes full plan before first write when unsupported operations appear.
- Blocks BD child→root and Term child→root parent clears.

See PR6 plan REVISIÓN 4 for bounded capability matrix and full-plan preflight.
