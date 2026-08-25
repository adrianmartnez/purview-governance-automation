# Unified Catalog Apply — Public Preview Contract Evidence

| Field | Value |
|-------|-------|
| Audit date | 2026-08-24 |
| Package version | `1.2.0` |
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

The offline contract harness and local normalization code were not used as primary
API evidence. Blogs and StackOverflow were not used as primary proof.

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

## Enforced v1.2 capability boundary

- Business Domain CREATE is not implemented
- Unsupported parent-clear operations fail closed
- Full-plan safety blocks unsupported operations before the first write
- Implementation is covered by offline contract tests
- No live-tenant validation claim
