# Foundation Libraries Architecture Review and Remediation Plan

> The phases in this file sequence foundation-package remediation only. They are
> unrelated to product [[Phase 2 - Insight Auditor and Replay]] and must be
> re-verified against current code before execution.

## Scope

- Included foundation libraries:
  - `auth`
  - `bridge`
  - `data-layer`
  - `data-model`
  - `database`
  - `hooks`
  - `http`
  - `icons`
  - `metrics`
  - `mocks`
  - `query-engine`
  - `sync-engine`
  - `utils`
- Excluded by decision for this remediation cycle:
  - `design-system`
  - `adapters`
  - `trackers`

## Dependency Graph Summary

### High-Level Forward Dependencies

- `utils`: foundational utility base, consumed broadly.
- `data-model`: foundational types/contracts base, consumed broadly.
- `database`: consumed by `data-layer`, `sync-engine`, `bridge`.
- `sync-engine`: consumed by `data-layer`.
- `bridge`: consumed by `data-layer`, `query-engine`.
- `data-layer`: consumed by `query-engine` hooks and app composition.
- `query-engine`: orchestration layer over builder/compiler/schema/hooks.
- `http`: independent transport library, now with explicit internal subpath export.
- `metrics`: consumes `data-model` + `utils` and instrumentation modules.
- `icons`, `hooks`, `mocks`, `auth`: leaf/support libraries.

### Reverse/Hub Observations

- `data-model` and `utils` are the shared core hubs.
- `data-layer` is the main integration hub for runtime data concerns.
- Runtime import graph remains acyclic across in-scope foundation libraries.

## Severity Buckets

## Critical

1. `foundation-metrics` buildability mismatch with source-first ecosystem

- Evidence:
  - `libs/foundation/metrics/package.json`
  - `libs/foundation/metrics/tsconfig.lib.json`
- Issue:
  - Dist-oriented package metadata and strictness override created lint/buildability drift against source-first foundation libraries.
- Remediation:
  - Normalized to source-first export map and restored strict TS behavior (`noImplicitOverride` no longer disabled).
  - Added library-scoped boundary lint configuration for `foundation-metrics` that preserves tag constraints while disabling buildable-only dependency checks for source-first imports.

2. `data-layer-plugin` generated API drift vs current `foundation-data-layer`

- Evidence:
  - `tools/data-layer-plugin/src/generators/crud/files/*`
  - `tools/data-layer-plugin/src/generators/crud/crud.ts`
  - `libs/foundation/data-layer/src/index.ts`
- Issue:
  - Templates referenced removed symbols (`useDLGetQuery`, `useDLMutatePost`, etc.) and imported `createQueryKeys` from the wrong package.
- Remediation:
  - Templates now generate wrappers around current APIs:
    - `useDLGet`/`useDLGetList`/`useDLGetOne`
    - `useDLCreate`/`useDLUpdate`/`useDLDelete`
  - Key factory import moved to `@open-zentra/foundation-data-model`.

3. `foundation-icons` compile blocker in registry contract

- Evidence:
  - `libs/foundation/icons/src/types.ts`
  - `libs/foundation/icons/src/registry/registry.ts`
- Issue:
  - `RegisterIconOptions.component` was broader than registry’s `LucideIcon` contract.
- Remediation:
  - `RegisterIconOptions.component` aligned to `LucideIcon`.
  - `src/test-setup.ts` excluded from library compilation scope.

## High

1. Fragmented HTTP transport injection

- Evidence:
  - `libs/foundation/data-layer/src/core/types.ts`
  - `libs/foundation/data-layer/src/core/container.ts`
  - `libs/foundation/sync-engine/src/network/index.ts`
  - `libs/foundation/metrics/src/instrumentation/network/retry-tracker.ts`
- Issue:
  - Multiple libraries had direct axios usage with no consistent injected instance path.
- Remediation:
  - Added optional `axiosInstance` injection support in:
    - `DataLayerConfig`
    - `SyncEngineConfig` and `NetworkMonitorConfig`
    - Metrics retry transport utility (`createRetryFetch`)
  - Wired through containers/providers for data-layer and sync-engine.

2. `foundation-http` internal API not export-mapped

- Evidence:
  - `libs/foundation/http/src/internal.ts`
  - `libs/foundation/http/package.json`
- Remediation:
  - Added explicit `./internal` subpath export.

## Medium

1. `foundation-query-engine` documented subpaths were not exported

- Evidence:
  - `libs/foundation/query-engine/src/index.ts`
  - `libs/foundation/query-engine/package.json`
- Remediation:
  - Added package exports for:
    - `./builder`
    - `./compiler`
    - `./engine`
    - `./hooks`
    - `./schema`
    - `./types`

2. Metrics type-import style debt

- Evidence:
  - `libs/foundation/metrics/src/types/compliance.ts`
  - `libs/foundation/metrics/src/types/context.ts`
- Remediation:
  - Replaced `import('...').Type` usage with `import type` declarations.

## Low

1. Documentation inconsistencies

- Evidence:
  - `libs/foundation/utils/README.md` (missing)
  - `libs/foundation/hooks/README.md` (placeholder)
  - `libs/foundation/mocks/README.md` (placeholder)
- Remediation:
  - Added/updated operational READMEs for maintainability.

## Per-Library Findings and Remediation

### `auth`

- State: no architectural boundary issues identified in this pass.
- Plan: keep current layering; fix local lint/test warnings only when touched.

### `bridge`

- State: stable integration layer between data-layer and database/analytics paths.
- Plan: no boundary changes required.

### `data-layer`

- Findings:
  - Needed explicit shared transport injection path.
- Implemented:
  - Added optional `axiosInstance` in `DataLayerConfig`.
  - Propagated into `DataLayerContainer` and file download service construction.
  - Forwarded to sync coordinator creation for network checks.

### `data-model`

- Findings:
  - Minor lint debt in tests.
- Implemented:
  - Removed unused type import in `foundation-error.spec.ts`.

### `database`

- State: stable in current dependency direction.
- Plan: no architectural refactor required in this cycle.

### `hooks`

- Findings:
  - Placeholder README.
- Implemented:
  - Replaced placeholder with concise purpose/usage docs.

### `http`

- Findings:
  - Internal entrypoint existed but not exported.
- Implemented:
  - Added `./internal` subpath export map entry.

### `icons`

- Findings:
  - Type mismatch blocked strict typecheck.
  - Test setup file under `src` should not be part of lib compilation.
- Implemented:
  - Registry registration type aligned to `LucideIcon`.
  - Excluded `src/test-setup.ts` from `tsconfig.lib.json`.

### `metrics`

- Findings:
  - Source-first mismatch vs rest of foundation packages.
  - Strictness override and type import style debt.
  - Needed injectable HTTP transport path for retry utility.
- Implemented:
  - Normalized package metadata to source-first export model.
  - Restored strict compile guard behavior.
  - Replaced import-type anti-pattern usage.
  - Added optional `axiosInstance` to `NetworkSignalConfig` and retry utility path.

### `mocks`

- Findings:
  - Placeholder README.
- Implemented:
  - Replaced placeholder with concise usage-focused docs.

### `query-engine`

- Findings:
  - Public docs and package export map diverged.
- Implemented:
  - Added documented subpath exports in package map.

### `sync-engine`

- Findings:
  - Health check path used direct axios with no shared injection path.
- Implemented:
  - Added optional `axiosInstance` to sync engine config interfaces.
  - Wired through container/coordinator/network monitor.
  - Network monitor now uses injected axios for `head` health checks when provided.

### `utils`

- Findings:
  - README missing despite broad internal usage.
- Implemented:
  - Added README covering module boundaries and anti-patterns.

## Cross-Library Interaction Fixes

1. Transport standardization

- Added optional shared axios injection in:
  - `data-layer`
  - `sync-engine`
  - `metrics` retry transport
- Enables app composition to pass one configured instance from `foundation-http`.

2. Tooling/API contract synchronization

- Updated `data-layer-plugin` templates and generator exports to current data-layer hook APIs.
- Moved key-factory import ownership to `foundation-data-model`.

3. Package export truthfulness

- `foundation-http`: now exports `./internal`.
- `foundation-query-engine`: now exports documented subpaths.

4. Source-first consistency

- `foundation-metrics` now follows same source-first package model as sibling foundation libraries.

## Public API / Interface Changes

1. `libs/foundation/data-layer/src/core/types.ts`

- Added:
  - `readonly axiosInstance?: AxiosInstance`

2. `libs/foundation/sync-engine/src/core/interfaces.ts`

- Added in `SyncEngineConfig`:
  - `axiosInstance?: AxiosInstance`

3. `libs/foundation/sync-engine/src/network/index.ts`

- Added in `NetworkMonitorConfig`:
  - `axiosInstance?: AxiosInstance`

4. `libs/foundation/metrics/src/types/config.ts`

- Added in `NetworkSignalConfig`:
  - `axiosInstance?: AxiosInstance`

5. `libs/foundation/metrics/src/instrumentation/network/retry-tracker.ts`

- Extended `createRetryFetch(...)` with optional injected axios instance parameter.

6. `libs/foundation/http/package.json`

- Added export:
  - `"./internal" -> "./src/internal.ts"`

7. `libs/foundation/query-engine/package.json`

- Added exports:
  - `./builder`, `./compiler`, `./engine`, `./hooks`, `./schema`, `./types`

8. `libs/foundation/icons/src/types.ts`

- Updated:
  - `RegisterIconOptions.component: LucideIcon`

## Validation Checklist

1. Type safety

- Run `tsc --noEmit` for in-scope foundation libraries.
- Confirm `foundation-icons` no longer emits the previous registry type mismatch.

2. Lint

- Run ESLint for in-scope foundation libraries.
- Confirm `foundation-metrics` no longer triggers buildability boundary violations.

3. Plugin output compatibility

- Generate CRUD hooks with `data-layer-plugin` and run `tsc --noEmit` on generated output.

4. Transport integration

- Verify data-layer file download path uses injected axios when configured.
- Verify sync-engine network health check uses injected axios when configured.
- Verify metrics retry-fetch utility supports injected axios path.

5. Dependency governance

- Keep runtime import graph acyclic.

## Execution Order

### Phase 1: Blockers

1. Fix metrics package model and strictness.
2. Fix icons type contract.
3. Align plugin templates to current data-layer APIs.

### Phase 2: Integration Alignment

1. Add and wire shared axios injection paths.
2. Correct package export maps for `http` and `query-engine`.

### Phase 3: Hardening and DX

1. Improve foundation docs consistency (`utils`, `hooks`, `mocks`).
2. Re-run full in-scope lint/typecheck and resolve residual warnings/errors.

## Assumptions

1. `design-system`, `adapters`, and `trackers` remain excluded from this cycle.
2. Source-first package metadata is the monorepo default.
3. Fixes prioritize architectural alignment over lint-rule suppression.
4. Backward behavior is preserved unless explicitly changed by API contract updates listed above.
