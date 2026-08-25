# Changelog

All notable changes to this project are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/),
and this project uses [Semantic Versioning](https://semver.org/) for the
**Python package**. Package SemVer is independent of machine-contract versions
(`purview-*-config/v1` + `/v2`, plan/result/remote-state `/v1` + `/v2`).
Contract `v1` does not mean package version `1.0.0`; a future package `1.x` may
keep contract `v1` while those artifacts remain compatible.

## [Unreleased]

### Added

- Unified Catalog **CLI v3** workflows: `config validate`, `remote-state capture`,
  `plan create` (requires `--remote-state-output` pair artifact), `plan inspect`,
  `apply` / `apply --apply` (requires `--remote-state`; `--credential` required for
  ready plans, not for blocked), and `result inspect`. Explicit `--credential`
  selectors (`azure-cli`, `azure-developer-cli`, `client-secret`, `certificate`);
  env material for client-secret/certificate uses `AZURE_CLIENT_ID` /
  `AZURE_CLIENT_SECRET` / `AZURE_CLIENT_CERTIFICATE_PATH` (tenant always from
  config/plan, never `AZURE_TENANT_ID`). Dual plan+remote persistence is
  fail-closed (not atomic). Offline reviewer guide:
  `docs/unified-catalog-reviewer-workflow.md`.
- Strict `load_remote_state_v3_text` / `load_remote_state_v3_file` for local
  planned remote-state/v3 artifacts.
- Offline CLI E2E and failure-matrix tests for v3; CI cli-integration smoke for
  fictional config/v3 validate and v3 help flags.

### Fixed

- Apply/v3 early `failed-before-write` paths (invalid remote / remote identity
  mismatch) now set `executionTargetContextIdentity` to the planned target so
  result serialization matches fail-closed semantics.
- Data Product and Glossary Term description drift reasons now use
  `canonical_json_scalar` so plan self-validation accepts description replaces.

- Controlled Unified Catalog **apply/v3** (`execute_governance_plan_v3`) with
  fail-closed full-plan preflight (P0–M), dry-run default, bounded write surface
  (Data Product and Glossary Term CREATE/safe REPLACE; Business Domain REPLACE
  only), `partial` execution-result/v3 status for pre-write interruption after
  successful writes, and `TenantBoundAuthorizationProvider` at the APPLY seam.
- `purview-execution-result/v3` schema, models, loader, and validation
  (including `partial` contiguous-prefix invariants).
- `derive_capture_recipe()` for exact fresh-capture replay from planned
  remote-state/v3 artifacts.
- Contract-test harness routes for targeted GET and bounded POST/PUT (no
  successful `POST /businessdomains`).
- `docs/contract-discovery/pr6-unified-catalog-apply.md` (Fase 0 safety gates).

### Changed

- README capability matrix documents apply/v3 bounded support and blocked-capability
  semantics (`executionEligibility: blocked` is not a planner error; executor
  fails closed before any write).

- Data Assets and Data Columns **read-model** capture in `purview-remote-state/v3`
  (PR5): opt-in `include_data_assets`, `include_data_columns`, and governance
  relationship families A–C via separate `readModelCoverage` (sparse positive-only).
- `enumerate_data_assets()`, `query_data_columns()`, and relationship list methods
  on `PurviewUnifiedCatalogClient` (read-only GET/POST query).
- Governance relationship normalization for `dataProductToDataAsset`,
  `glossaryTermToDataAsset`, and `glossaryTermToDataColumn` (Related only).
- Glossary Terms declarative modeling in contract **v3** (planning + controlled apply):
  config desired state, opt-in remote capture (Shapes C/D), diff, plan with
  domain/parent dependency resolution, scoped hierarchy validation, and
  deterministic operation ordering after Business Domains and Data Products.
  Apply supports CREATE and safe REPLACE (parent-clear blocked fail-closed).
- `enumerate_glossary_terms()` on `PurviewUnifiedCatalogClient`.
- Opt-in remote capture `include_glossary_terms=True` (Shape C); Shape D when
  combined with `include_data_products=True`; default capture remains Shape A.
- Glossary Term policy: **parentId full ownership** (absent = root intent),
  **acronyms three-state** optional explicit ownership, remote `null` fail-closed,
  duplicate names allowed (UUID-only matching), domain move blocked, deferred
  configurables safety, status safety-only.
- Data Products declarative modeling in contract **v3** (planning-only; no apply):
  config desired state, opt-in remote capture (Shape B), diff, and plan with
  domain dependency resolution and deterministic operation ordering.
- `enumerate_data_products()` on `PurviewUnifiedCatalogClient` (14 official
  `CatalogModelDataProductTypeEnum` values from API `2026-03-20-preview`).
- Opt-in remote capture `include_data_products=True` (Shape B); default capture
  remains Business Domain–only (Shape A, PR2 compatible).
- Data Product safety: `status` / `provisioningState`, deferred configurables,
  owner/audience canonicalization, domain move fail-closed policy.
- Business Domains declarative modeling via contract **v3**:
  `purview-governance-config/v3`, `purview-remote-state/v3`,
  `purview-governance-plan/v3` (planning-only; no apply).
- Unified Catalog target binding with declared `target.tenantId` and
  `compute_target_context_identity_v3` (separate from frozen v1/v2 Scanning
  target identity).
- Deterministic diff/plan for Business Domains: parentId root ownership,
  description v2-semantics, explicit `isRestricted` ownership,
  `UnsupportedConfigurableField` safety for deferred configurables,
  hierarchy limits (depth 5, count 200 including uninterpreted remotes),
  name-conflict CREATE blocking.
- Example `examples/fictional-governance-config-v3.yaml` and offline UC contract
  tests extended for Business Domains v3 capture/plan.
- `unified_catalog` package with `PurviewUnifiedCatalogClient`, fail-closed
  production endpoint policy (`https://api.purview-service.microsoft.com`),
  Public Preview API `2026-03-20-preview`, compatibility metadata, and
  read-only `enumerate_business_domains()` contract proof.
- Offline Unified Catalog loopback contract server and tests (isolated from
  Scanning contract harness).

### Changed

- Package development version `1.2.0.dev0`.

### Fixed

- README CI badge and package author metadata (`adrianmartnez`).

### Safety

- Unified Catalog Business Domains v3 is **planning-only**; no REST writes, no
  apply, no CLI UC workflow. `executionEligibility: ready` indicates absence of
  known v3 blockers — not Microsoft execution guarantee. Declared `tenantId` is
  not live-verified against credentials in PR2. REPLACE blocked when deferred
  configurables would be clobbered.
- Unified Catalog client secret-sentinel coverage; bearer tokens are not
  persisted; Authorization is excluded from sanitized errors and contract
  recordings.

## [1.1.0] - 2026-08-11

First stable package release of Scanning and Classification as Code
(multi-resource config/remote-state/plan/apply v2).

### Added

- Config / remote-state / plan **v2** contracts for AzureStorage **Data Sources**,
  AzureStorageMsi **Scans**, **Custom AzureStorage Scan Rule Sets**, and
  **Custom Classification Rules** (read, compare, deterministic plan, and
  controlled apply).
- Multi-resource desired-vs-remote comparison (data sources, classification
  rules, scans, scan rule sets), including composite Scan identity and
  deterministic prerequisite ordering.
- Controlled multi-resource apply for `purview-governance-plan/v2` with dry-run
  default, explicit apply opt-in, fresh `purview-remote-state/v2` staleness gate,
  fail-closed writes, and `purview-execution-result/v2`.
- Loopback contract coverage for Scan, Scan Rule Set, and Classification Rule
  list/get/create-or-replace (including pagination fail-closed cases, contract-
  tested failure classes, and idempotent re-planning).
- Public multi-resource example `examples/fictional-governance-config-v2.yaml`
  and offline CLI reviewer workflow
  `tests/cli/test_offline_v2_workflow.py` (validate → independent remote
  capture → plan create/inspect → dry-run → explicit apply → result inspect →
  empty re-plan → no-op apply; no Azure credentials).

### Changed

- `purview-remote-state/v2` shape expands with required `classificationRules`
  and `uninterpretedClassificationRules`.
- `purview-governance-plan/v2` desired state requires `classificationRules`.
  Pre-#27 plan/v2 development documents without that key are rejected on load
  with `plan.development_shape_superseded` (no upconvert).

### Safety / limitations

- Apply dispatches by plan version: plan/v1 → execution-result/v1 (frozen);
  plan/v2 → execution-result/v2. Dry-run remains the default; mutation requires
  explicit opt-in. No automatic deletes, retries, rollback, or Tag Classification
  Version.
- Explicit unsupported Scan configurable fields block safe comparison
  (`remote.unsupported_configurable_field`).
- No claim of validation against a live Microsoft Purview tenant. Offline
  contract tests are not production or live Microsoft Purview validation.

## [1.0.0] - 2026-08-10

First stable package release of the Purview Automation Foundation vertical slice.

### Foundation

- Installable Python 3.12 package with `src/` layout, wheel, and sdist.
- Five protected CI gates: `lint`, `unit-tests`, `package-validation`,
  `api-contract-tests`, `cli-integration`.

### Config

- Versioned governance configuration `purview-governance-config/v1`.
- Deterministic validation and normalization.
- AzureStorage Data Source vertical slice.

### Auth

- Microsoft Entra boundary via `DefaultAzureCredential`.
- Purview scope `https://purview.azure.net/.default`.
- Credentials remain external to committed configuration.

### Scanning client

- Purview Scanning Data Plane client pinned to API version `2023-09-01`.
- Public Data Sources List/Get.
- Package-private create-or-replace primitive with receipt (not a public export).
- Bounded timeouts, no redirect following, sanitized errors.

### Remote state

- Canonical artifact `purview-remote-state/v1`.
- Material state identity for staleness checks.

### Diff

- Desired-vs-remote outcomes: create, replace, no-op, remote-only, blocked.
- No automatic delete path.

### Plan

- Versioned plan artifact `purview-governance-plan/v1`.
- Deterministic plan identity and inspectable operation list.
- Target, config, desired, and remote identities recorded in the plan.

### Apply

- Safe explicit apply via `execute_governance_plan`.
- Dry-run default; mutation requires explicit apply mode.
- Target validation and remote-state staleness checks before writes.
- Mutation payloads taken from the plan desired snapshot (payload authority).
- HTTP 200/201 treated as confirmed writes; explicit 4xx as write-failed;
  5xx/transport/unexpected outcomes as unknown/indeterminate.
- No automatic mutation retry; no auto-replan.
- Partial and indeterminate outcomes recorded truthfully for audit.

### Result

- Execution result artifact `purview-execution-result/v1`.
- `resultIdentity` plus planned vs execution target/remote provenance.
- `writesPerformed` / `writesAttempted` / `writesUnknown` counters.

### CLI

- `config validate`
- `remote-state capture`
- `plan create` / `plan inspect`
- `apply` (dry-run default) / `apply --apply`
- `result inspect`
- Exit codes `0`–`7` as documented in the README.

### Security and safety

- No secrets in committed configuration or machine artifacts.
- Sanitized error surfaces.
- No automatic delete reconciliation.
- No insecure public loopback override flags on the CLI.

### Testing

- Deterministic loopback Purview contract-test server.
- Offline reviewer workflow without a live Microsoft Purview account.
- Default CI does not require Azure credentials or a commercial tenant.

### Known limitations

- AzureStorage Data Source kind only.
- Scans, scan rule sets, and classifications are not implemented (v1.1 scope).
- Unified Catalog is not implemented (v1.2 scope).
- No automatic deletes.
- Residual TOCTOU between final remote read and first write (no ETag/CAS).
- No automatic mutation retry.
- No production-scale operational claim.
- No claim of validation against a live Microsoft Purview tenant.
