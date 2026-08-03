# @open-zentra/foundation-data-model

Canonical contract package for Open Zentra foundation libraries.

## Purpose

`foundation-data-model` is the single source of truth for:

- Shared runtime constants and derived type aliases
- Cross-library contracts for sync and database domains
- Branded primitives and IDs
- Query-key construction and hashing helpers
- Foundation error codes/categories and base error utilities
- Validation result contracts

Consumers include `foundation-database`, `foundation-sync-engine`, `foundation-data-layer`, `foundation-query-engine`, `foundation-bridge`, `foundation-http`, `foundation-auth`, and `foundation-mocks`.

## Installation

```bash
npm i @open-zentra/foundation-data-model
```

## Constants-Only Contract Model

Fixed-option domains are expressed with `UPPER_SNAKE_CASE` `as const` objects and PascalCase type aliases derived from them.

Examples:

- `CONFLICT_STRATEGY` + `type ConflictStrategy`
- `SYNC_EVENT_TYPE` + `type SyncEventType`
- `QUERY_CACHE_STATUS` + `type QueryCacheStatus`
- `MUTATION_TYPE` + `type MutationType`
- `FOUNDATION_ERROR_CODE` + `type FoundationErrorCode`

Pattern:

```ts
import type { ValueOf } from '@open-zentra/foundation-data-model';

export const MY_DOMAIN = {
  A: 'a',
  B: 'b',
} as const;

export type MyDomain = ValueOf<typeof MY_DOMAIN>;
```

## Shared Database Contracts

Location: `src/types/database.ts`

Value constants:

- `QUERY_CACHE_STATUS`
- `MUTATION_STATUS`
- `MUTATION_TYPE`
- `OPFS_FILE_TYPE`
- `SYNC_STATE_KEY`

Derived types:

- `QueryCacheStatus`
- `MutationStatus`
- `MutationType`
- `OpfsFileType`
- `SyncStateKey`

Interfaces/helpers:

- `DuckDBViewDefinition`
- `DuckDBViewsValue`
- `LastSyncValue`
- `TableSyncMetadataEntry`
- `createTableSyncMetadataEntry(...)`
- `needsTableUpdate(...)`
- `getFilesNeedingDownload(...)`

Usage:

```ts
import {
  createTableSyncMetadataEntry,
  MUTATION_STATUS,
  MUTATION_TYPE,
  OPFS_FILE_TYPE,
  SYNC_STATE_KEY,
} from '@open-zentra/foundation-data-model';

const entry = createTableSyncMetadataEntry('events', Date.now(), {
  'events-2026-01.parquet': 'abc123',
});

const mutation = {
  type: MUTATION_TYPE.CREATE,
  status: MUTATION_STATUS.PENDING,
  fileType: OPFS_FILE_TYPE.PARQUET,
  key: SYNC_STATE_KEY.PENDING_COUNT,
};

void entry;
void mutation;
```

## Shared Sync Contracts

Location: `src/types/sync.ts`

Value constants:

- `CONFLICT_STRATEGY`
- `CONFLICT_WINNER`
- `SYNC_EVENT_TYPE`
- `CROSS_TAB_MESSAGE_TYPE`
- `OFFLINE_QUERY_SOURCE`

Derived types:

- `ConflictStrategy`
- `ConflictWinner`
- `SyncEventType`
- `CrossTabMessageType`
- `OfflineQuerySource`

Key interface bindings:

- `ConflictResult.winner: ConflictWinner`
- `OfflineQueryContext.source: OfflineQuerySource`

Usage:

```ts
import {
  CONFLICT_STRATEGY,
  CONFLICT_WINNER,
  OFFLINE_QUERY_SOURCE,
  type ConflictResult,
  type OfflineQueryContext,
} from '@open-zentra/foundation-data-model';

const result: ConflictResult<{ id: string }> = {
  resolvedData: { id: '1' },
  winner: CONFLICT_WINNER.SERVER,
  requiresReview: false,
};

const context: OfflineQueryContext = {
  isOffline: true,
  isStale: false,
  source: OFFLINE_QUERY_SOURCE.OFFLINE_DB,
  cachedAt: Date.now(),
};

void CONFLICT_STRATEGY.LAST_WRITE_WINS;
void result;
void context;
```

## Error Contracts

Value constants:

- `FOUNDATION_ERROR_CODE`
- `ERROR_CATEGORY`

Derived types:

- `FoundationErrorCode`
- `ErrorCategory`

Utilities:

- `getErrorCategory(code)`
- `isRetryableErrorCode(code)`
- `FoundationError` and related guards/helpers

## Query-Key Contracts

`QUERY_SCOPE` is the canonical fixed-option contract for query-scope metadata.

Provided helpers:

- `createQueryKeys(...)`
- `createAnalyticsQueryKey(...)`
- `extractQueryKeyMeta(...)`
- `hashQueryKey(...)`

## Validation Contracts

Value constant:

- `VALIDATION_SEVERITY`

Derived type:

- `ValidationSeverity`

Result model:

- `ValidationResultData` (`valid` + structured `issues`)
- `ValidationResult` utility constructors (`success`, `failure`, `fromErrors`, `merge`, ...)

## Architecture

Top-level modules:

- `src/types/*`: contracts and shared constants
- `src/errors/*`: foundation error model
- `src/query-keys/*`: query key contracts and hashing
- `src/schemas/*`: schema definitions
- `src/datasource/*`: datasource shape helpers

Design rules:

1. No `enum` exports for fixed options.
2. No fixed-option string-literal unions hand-written in consumers.
3. No constant/type name collisions for fixed-option domains.
4. Shared contracts live here first, then are consumed by other foundation libraries.

## Migration Notes

If you previously imported fixed-option values by PascalCase names, migrate to constants:

- `ConflictStrategy.SERVER_WINS` -> `CONFLICT_STRATEGY.SERVER_WINS`
- `MutationType.CREATE` -> `MUTATION_TYPE.CREATE`
- `FoundationErrorCode.CONFIG_INVALID` -> `FOUNDATION_ERROR_CODE.CONFIG_INVALID`

Keep PascalCase type annotations:

- `conflictStrategy: ConflictStrategy`
- `type: MutationType`
- `code: FoundationErrorCode`

## Verification

```bash
npx tsc -p libs/foundation/data-model/tsconfig.lib.json --pretty false
npx vitest run libs/foundation/data-model/src/**/*.spec.ts
rg "export enum" libs/foundation/data-model/src
```

`rg "export enum"` should return no matches.

## Contribution Guidance

1. Add shared cross-library contracts here before adding local copies elsewhere.
2. Prefer direct imports from concrete modules inside implementations; use barrels for package surface only.
3. Keep runtime string values stable for backward wire compatibility unless an explicit migration is planned.
4. Add/adjust tests when introducing or renaming shared constants.
