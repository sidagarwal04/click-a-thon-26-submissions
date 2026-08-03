# @open-zentra/foundation-database

Offline-first persistence for Open Zentra. This library provides the Dexie/IndexedDB database, typed table contracts, service-layer operations, OPFS metadata coordination, and singleton lifecycle management used by foundation consumers.

## Table of Contents

1. [Purpose](#purpose)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Public API](#public-api)
5. [Architecture](#architecture)
6. [Schema, Migrations, and Indexes](#schema-migrations-and-indexes)
7. [Configuration](#configuration)
8. [Error Handling](#error-handling)
9. [Performance Notes](#performance-notes)
10. [Testing and Verification](#testing-and-verification)
11. [Contributing](#contributing)

## Purpose

Use this package when you need:

- Persistent query cache with TTL + stale/fresh status
- Durable offline mutation queue with idempotency protection
- Typed sync-state storage for cross-session sync context
- OPFS file metadata tracking and OPFS manager integration
- A stable singleton lifecycle (`DatabaseFacade` + raw `InsightsDatabase`) backed by one shared singleton source

## Installation

```bash
npm i @open-zentra/foundation-database @open-zentra/foundation-data-model
```

Peer/runtime dependencies used internally:

- `dexie`
- `zod`
- `@open-zentra/foundation-utils`

## Quick Start

### Recommended: Facade API

```ts
import {
  DATABASE_TRANSACTION_MODE,
  DATABASE_TRANSACTION_TABLE,
  getDatabaseFacade,
  MUTATION_STATUS,
  MUTATION_TYPE,
} from '@open-zentra/foundation-database';

const facade = getDatabaseFacade({ debug: true });

await facade.transaction(
  DATABASE_TRANSACTION_MODE.READ_WRITE,
  [DATABASE_TRANSACTION_TABLE.QUERIES, DATABASE_TRANSACTION_TABLE.MUTATIONS],
  async () => {
    await facade.queries.set({
      queryHash: 'users:list',
      queryKey: ['users', 'list'],
      data: [{ id: 'u1', name: 'Ada' }],
      tableName: 'users',
      timestamp: Date.now(),
      dataUpdatedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    await facade.mutations.add({
      id: 'm1',
      type: MUTATION_TYPE.CREATE,
      tableName: 'users',
      entityId: 'u1',
      payload: { id: 'u1', name: 'Ada' },
      timestamp: Date.now(),
      status: MUTATION_STATUS.PENDING,
      retryCount: 0,
      maxRetries: 3,
      idempotencyKey: 'users:u1:create',
    });
  },
);
```

### Raw database (internal foundation usage)

```ts
import { getDatabase } from '@open-zentra/foundation-database';

const db = getDatabase();
const count = await db.queries.count();
```

## Public API

### Facade and lifecycle

- `getDatabaseFacade(config?)`
- `resetDatabaseFacade()`
- `hasDatabaseFacade()`
- `DatabaseFacade`

### Transaction constants

- Import from `@open-zentra/foundation-data-model`:
  - `DATABASE_TRANSACTION_MODE`
    - `READ`
    - `READ_WRITE`
  - `DATABASE_TRANSACTION_TABLE`
    - `QUERIES`
    - `MUTATIONS`
    - `SYNC_STATE`
    - `OPFS_FILES`
    - `TABLE_SYNC_METADATA`

### Shared database constants and helpers

Import these directly from `@open-zentra/foundation-data-model`:

- `QUERY_CACHE_STATUS`
- `MUTATION_STATUS`
- `MUTATION_TYPE`
- `OPFS_FILE_TYPE`
- `SYNC_STATE_KEY`
- `createTableSyncMetadataEntry`
- `needsTableUpdate`
- `getFilesNeedingDownload`

### Services

- `facade.queries`: query cache operations (`get`, `bulkGet`, `set`, `bulkSet`, `delete`, `deleteByTable`, `deleteExpired`, `clear`, ...)
- `facade.mutations`: mutation queue operations (`add`, `addIfNotExists`, `getPending`, `updateStatus`, `findByIdempotencyKey`, ...)
- `facade.syncState`: typed sync-state operations (`get`, `set`, `getLastSync`, `setLastSync`, `getDuckDBViews`, ...)
- `facade.opfsMetadata`: OPFS metadata operations (`getByTable`, `getViews`, `markRegistered`, `getInDependencyOrder`, ...)
- `facade.tableSyncMetadata`: table sync metadata CRUD and batch retrieval

### OPFS manager

- `getOpfsManager(config?)`
- `resetOpfsManager()`
- `hasOpfsManager()`
- `OpfsManager`

### Error utilities

- `DatabaseError`
- `isDatabaseError()`
- `isQuotaExceededError()`
- `OpfsNotSupportedError`
- `OpfsInitFailedError`

## Architecture

### Layers

1. `core/`: Dexie database, config, singleton factory lifecycle
2. `tables/`: table contracts + helpers
3. `services/`: validation + data access logic
4. `facade/`: consumer-facing orchestrator with transaction boundary
5. `opfs/`: OPFS directory/file manager that delegates metadata persistence through services

### Shared contract ownership

`foundation-database` consumes canonical shared contracts from `@open-zentra/foundation-data-model` (`src/types/database.ts`) and does not proxy those symbols.

### Ownership matrix

| Contract                                                  | Canonical owner         | Import from                                |
| --------------------------------------------------------- | ----------------------- | ------------------------------------------ |
| `MUTATION_STATUS`, `MUTATION_TYPE`, `OPFS_FILE_TYPE`      | `foundation-data-model` | `@open-zentra/foundation-data-model` |
| `SYNC_STATE_KEY`                                          | `foundation-data-model` | `@open-zentra/foundation-data-model` |
| `DATABASE_TRANSACTION_MODE`, `DATABASE_TRANSACTION_TABLE` | `foundation-data-model` | `@open-zentra/foundation-data-model` |
| `MutationQueueEntry`, `CreateMutationOptions`             | `foundation-data-model` | `@open-zentra/foundation-data-model` |

### Singleton safety

- `getDatabase()` and `getDatabaseFacade()` resolve to the same `InsightsDatabase` singleton.
- `resetDatabaseFacade()` resets both facade and database singletons for deterministic lifecycle behavior.
- No registry callback layer is used, which removes cross-singleton drift vectors.

## Schema, Migrations, and Indexes

Current Dexie schema versions in `src/core/database.ts`:

- `v1`: `queries`, `mutations`, `opfsFiles`, `syncState`
- `v2`: adds `tableSyncMetadata`
- `v3`: adds hot-path indexes

Hot-path indexes:

- `mutations`: `[status+timestamp]`
- `opfsFiles`: `isRegistered`, `fileType`
- `tableSyncMetadata`: `lastIngestedAt`

These indexes are used to reduce in-memory filtering and improve scan performance for queue/state synchronization flows.

## Configuration

`DatabaseConfig` defaults are defined in `src/core/config.ts`.

| Key                   |            Default | Meaning                                  |
| --------------------- | -----------------: | ---------------------------------------- |
| `name`                | `open-zentra-db` | IndexedDB database name                  |
| `version`             |                `1` | Config version marker                    |
| `debug`               |          env-based | Enables debug logging                    |
| `queryCacheTTL`       |       `5 * 60_000` | Query cache TTL                          |
| `staleThreshold`      |           `60_000` | Fresh vs stale threshold                 |
| `maxRetryAttempts`    |                `3` | Mutation retry cap                       |
| `autoCleanup`         |             `true` | Enables interval cleanup                 |
| `cleanupInterval`     |           `60_000` | Cleanup cadence                          |
| `maxCacheEntries`     |             `1000` | LRU cap (0 disables)                     |
| `mutationRetentionMs` |      `60 * 60_000` | Retention for completed/failed mutations |

Example:

```ts
import { getDatabaseFacade } from '@open-zentra/foundation-database';

const facade = getDatabaseFacade({
  debug: false,
  queryCacheTTL: 10 * 60_000,
  maxCacheEntries: 500,
});
```

## Error Handling

Database errors use `FOUNDATION_ERROR_CODE.DATABASE_*` codes from `foundation-data-model`.

Example pattern:

```ts
import { getDatabaseFacade, isQuotaExceededError } from '@open-zentra/foundation-database';

try {
  await getDatabaseFacade().queries.clear();
} catch (error) {
  if (isQuotaExceededError(error)) {
    // trigger eviction/retry strategy
  }
  throw error;
}
```

For functional error flow, use the shared `Result` contract (`ok`/`error`) from `@open-zentra/foundation-data-model`.

## Performance Notes

- Query cache cleanup combines TTL deletion and optional LRU eviction.
- Mutation cleanup removes terminal states after retention.
- OPFS metadata lookups use indexed paths for `fileType` and schema-backed operations.
- Services share a common validation helper to avoid duplicated parse/throw logic.

## Testing and Verification

Typical local checks:

```bash
npx tsc -p libs/foundation/data-model/tsconfig.lib.json --pretty false
npx tsc -p libs/foundation/database/tsconfig.lib.json --pretty false
npx vitest run libs/foundation/database/src/**/*.spec.ts
```

Consumer smoke checks:

```bash
npx tsc -p libs/foundation/sync-engine/tsconfig.lib.json --pretty false
npx tsc -p libs/foundation/data-layer/tsconfig.lib.json --pretty false
npx tsc -p libs/foundation/bridge/tsconfig.lib.json --pretty false
```

## Contributing

1. Keep shared database contracts in `foundation-data-model` (`src/types/database.ts`), not local duplicates.
2. Prefer direct imports internally; avoid unnecessary barrel dependency chains.
3. Use enums/constants for fixed option sets; avoid string-literal union duplication.
4. Add tests for lifecycle regressions (singleton reset/accessor coherence), schema/index behavior, and helper contract consistency.
5. Keep `src/index.ts` focused on database-owned APIs and avoid cross-foundation proxy exports.
