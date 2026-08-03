---
name: Query Engine Enterprise Architecture v2
overview: Complete enterprise-grade Query Engine with intelligent routing (API vs DuckDB), real-time Convex WebSocket subscriptions, full sync-engine integration with optimistic updates and conflict resolution, DataSource API for Parquet files with lastIngestedAt, stale-while-revalidate caching, and cross-tab synchronization.
todos:
  - id: phase1-types
    content: Define all TypeScript types (DimensionSpec, MeasureSpec, EnterpriseQuery, TableConfig, DataSourceResponse, etc.)
    status: pending
  - id: phase2-schema-registry
    content: Create SchemaRegistry with table configurations, API references, and load state management
    status: pending
  - id: phase3-table-extractor
    content: Implement table extraction from query members (dimensions, measures, filters, joins)
    status: pending
  - id: phase4-decision-engine
    content: Create DecisionEngine with routing logic (API vs DuckDB)
    status: pending
  - id: phase5-api-executor
    content: Create ApiExecutor for Convex API calls with filter translation
    status: pending
  - id: phase6-file-manager
    content: Create FileManager for Parquet downloads, OPFS storage, stale-while-revalidate
    status: pending
  - id: phase7-sql-compiler
    content: Update SqlCompiler for object-based specs and joins
    status: pending
  - id: phase8-duckdb-executor
    content: Create DuckDBExecutor for SQL execution
    status: pending
  - id: phase9-optimistic-updater
    content: Create OptimisticUpdater for immediate UI updates
    status: pending
  - id: phase10-rollback-manager
    content: Create RollbackManager for reverting failed mutations
    status: pending
  - id: phase11-query-orchestrator
    content: Create QueryOrchestrator that coordinates entire flow
    status: pending
  - id: phase12-use-query-engine
    content: Implement useQueryEngine with Convex reactive subscriptions
    status: pending
  - id: phase13-use-mutate-query-engine
    content: Implement useMutateQueryEngine with full sync-engine integration
    status: pending
  - id: phase14-use-upload-file
    content: Implement useUploadFile for local file management
    status: pending
  - id: phase15-query-engine-provider
    content: Create QueryEngineProvider with all dependencies
    status: pending
  - id: phase16-exports
    content: Update public API exports
    status: pending
isProject: true
---

# Query Engine: Enterprise Architecture v2

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Principles](#2-core-principles)
3. [Architecture Overview](#3-architecture-overview)
4. [Type Definitions](#4-type-definitions)
5. [Decision Engine](#5-decision-engine)
6. [Query Execution Paths](#6-query-execution-paths)
7. [SchemaRegistry](#7-schemaregistry)
8. [Parquet File Management](#8-parquet-file-management)
9. [Real-Time Updates](#9-real-time-updates)
10. [Sync Engine Integration](#10-sync-engine-integration)
11. [Hooks Implementation](#11-hooks-implementation)
12. [Provider Implementation](#12-provider-implementation)
13. [File Structure](#13-file-structure)

---

## 1. Executive Summary

An enterprise-grade Query Engine providing:

| Feature | Description |

|---------|-------------|

| **Intelligent Routing** | Auto-routes to API (simple) or DuckDB (complex) based on query analysis |

| **Real-Time Updates** | Convex WebSocket subscriptions for instant data refresh |

| **Full Offline Support** | Query cached data, queue mutations, auto-sync on reconnect |

| **Optimistic Updates** | Show changes immediately, auto-rollback on failure |

| **Conflict Resolution** | Configurable per-table strategies (server-wins, client-wins, merge, manual) |

| **Cross-Tab Sync** | Coordinate state across browser tabs via BroadcastChannel |

| **Stale-While-Revalidate** | Use cached Parquet files, check for updates in background |

| **Two Hooks** | `useQueryEngine` (declarative) + `useMutateQueryEngine` (imperative) |

| **Object-Based Format** | Type-safe DimensionSpec and MeasureSpec objects |

| **Table Inference** | Tables extracted from query members, never specified explicitly |

---

## 2. Core Principles

### 2.1 Prefer API for Simple Queries

Even if Parquet files exist locally, simple queries use the Convex API because:

- **Fresh data** - Real-time via WebSocket
- **Simpler execution** - No file management
- **Uses existing infrastructure** - Leverages Convex's optimized engine

### 2.2 Use DuckDB Only When Necessary

Route to DuckDB only when:

- Query has **joins** (multiple tables)
- Query has **measures** (aggregations)
- Table has **no API** defined
- Table is **local-only** (user-uploaded)

### 2.3 Tables Inferred from Query

Tables are **never** specified explicitly. Extracted from:

- `dimensions` → `{ member: 'users.name' }` → table: `users`
- `measures` → `{ member: 'orders.amount', aggregation: 'sum' }` → table: `orders`
- `filters` → `{ member: 'products.status', ... }` → table: `products`
- `joins` → `{ left: 'orders.user_id', right: 'users.id' }` → tables: `orders`, `users`

### 2.4 Parquet Files from Backend Only

We **never** convert JSON to Parquet in browser:

1. Backend generates Parquet files
2. Stores in S3 / Convex file storage
3. Client downloads via DataSource API
4. Stores in OPFS for offline access
5. Registers as DuckDB virtual tables

### 2.5 Stale-While-Revalidate

For DuckDB path:

1. Use cached files immediately
2. Check `lastIngestedAt` in background
3. Download if newer version exists
4. Notify via `hasNewerData` flag

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER APPLICATION                                │
│                                                                              │
│  const { data } = useQueryEngine({                                          │
│    dimensions: [{ member: 'users.name' }],                                  │
│    filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],│
│  });                                                                         │
│                                                                              │
│  const { mutate } = useMutateQueryEngine();                                 │
│  await mutate({ operation: 'create', dimensions: [...], data: {...} });    │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUERY ENGINE LAYER                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                       QueryEngineProvider                                ││
│  │                                                                          ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   ││
│  │  │TableExtractor│ │DecisionEngine│ │SchemaRegistry│ │QueryOrchestrator│ ││
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   ││
│  │                                                                          ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   ││
│  │  │ ApiExecutor  │ │ FileManager  │ │ SqlCompiler  │ │DuckDBExecutor│   ││
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   ││
│  │                                                                          ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                     ││
│  │  │ Optimistic   │ │  Rollback    │ │Cross-Tab Sync│                     ││
│  │  │  Updater     │ │  Manager     │ │  (from sync) │                     ││
│  │  └──────────────┘ └──────────────┘ └──────────────┘                     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FOUNDATION LIBRARIES                                 │
│                                                                              │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐│
│  │foundation-data-│ │foundation-sync-│ │foundation-     │ │foundation-     ││
│  │layer           │ │engine          │ │bridge          │ │database        ││
│  │                │ │                │ │                │ │                ││
│  │- ConvexClient  │ │- OfflineQueue  │ │- DuckDBRouter  │ │- QueryCache    ││
│  │- QueryClient   │ │- SyncCoord     │ │- WorkerPool    │ │- MutationQueue ││
│  │- DataLayer     │ │- ConflictRes   │ │- AnalyticsOpfs │ │- SyncState     ││
│  │  Container     │ │- CrossTabMgr   │ │                │ │                ││
│  └────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                                     │
│                                                                              │
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐       │
│  │     IndexedDB      │ │       OPFS         │ │      Convex        │       │
│  │                    │ │                    │ │                    │       │
│  │ - Query cache      │ │ - Parquet files    │ │ - Source of truth  │       │
│  │ - Mutation queue   │ │ - Local uploads    │ │ - Real-time sync   │       │
│  │ - Sync state       │ │ - DuckDB database  │ │ - API endpoints    │       │
│  └────────────────────┘ └────────────────────┘ └────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Unified Table Registry (Single Source of Truth)

### 4.1 Problem: Table Metadata Duplication

Currently, table metadata is scattered across multiple places:

| Library | What it stores | Where |

|---------|---------------|-------|

| DataLayer | `mutationMap` (create/update/delete refs) | In-memory config |

| SyncEngine | `tableStrategies`, `tableMergeConfigs` | In-memory config |

| QueryEngine | `SchemaRegistry` (measures, dimensions) | In-memory |

| Database | `tableName` in queries/mutations/opfsFiles | IndexedDB |

### 4.2 Solution: UnifiedTableConfig in DataLayerConfig

All table metadata is defined **ONCE** in `DataLayerConfig.tables`:

```typescript
// libs/foundation/data-layer/src/core/types.ts (EXTENDED)

import type { ConflictStrategy, MergeConfig } from '@foundation/sync-engine';
import type { FunctionReference } from 'convex/server';

/**
 * Unified table configuration - single source of truth
 */
export interface UnifiedTableConfig {
  /** Table name (e.g., 'users', 'orders') */
  readonly name: string;

  // ── CONVEX API REFERENCES ──────────────────────────────────────────────────
  readonly convex?: {
    readonly list?: FunctionReference<'query'>;
    readonly get?: FunctionReference<'query'>;
    readonly create?: FunctionReference<'mutation'>;
    readonly update?: FunctionReference<'mutation'>;
    readonly delete?: FunctionReference<'mutation'>;
  };

  // ── CACHE CONFIGURATION ────────────────────────────────────────────────────
  readonly staleTime?: number; // Per-table stale time (ms)
  readonly gcTime?: number; // Per-table GC time (ms)

  // ── CONFLICT RESOLUTION ────────────────────────────────────────────────────
  readonly conflictStrategy?: ConflictStrategy; // Per-table strategy
  readonly mergeConfig?: MergeConfig; // For 'merge' strategy

  // ── ANALYTICS (for QueryEngine DuckDB path) ────────────────────────────────
  readonly analytics?: {
    readonly enabled: boolean;
    readonly freshness?: 'realtime' | 'near-realtime' | 'eventual';
    readonly staleTime?: number; // Analytics-specific stale time
  };
}

/**
 * Extended DataLayerConfig with unified table registry
 */
export interface DataLayerConfig {
  readonly convexUrl: string;

  /**
   * Unified table registry - single source of truth.
   * Replaces the old `mutationMap` approach.
   */
  readonly tables?: ReadonlyArray<UnifiedTableConfig>;

  // Global defaults
  readonly conflictStrategy?: ConflictStrategy;
  readonly defaultStaleTime?: number;
  readonly defaultGcTime?: number;

  // Feature flags
  readonly enableCrossTab?: boolean;
  readonly enableAnalytics?: boolean;
  readonly debug?: boolean;

  /** @deprecated Use `tables` instead */
  readonly mutationMap?: Record<string, TableMutations>;
}
```

### 4.3 TableRegistry Class

```typescript
// libs/foundation/data-layer/src/core/table-registry.ts

export class TableRegistry {
  private readonly tables: Map<string, UnifiedTableConfig> = new Map();
  private readonly defaults: {
    staleTime: number;
    gcTime: number;
    conflictStrategy: ConflictStrategy;
  };

  constructor(tables: ReadonlyArray<UnifiedTableConfig> = [], defaults = {}) {
    this.defaults = {
      staleTime: defaults.staleTime ?? 5 * 60 * 1000,
      gcTime: defaults.gcTime ?? 24 * 60 * 60 * 1000,
      conflictStrategy: defaults.conflictStrategy ?? 'last-write-wins',
    };
    for (const table of tables) {
      this.tables.set(table.name, table);
    }
  }

  // ── BASIC ACCESSORS ────────────────────────────────────────────────────────
  getTable(name: string): UnifiedTableConfig | undefined;
  getTableOrThrow(name: string): UnifiedTableConfig;
  hasTable(name: string): boolean;
  getAllTables(): ReadonlyArray<UnifiedTableConfig>;

  // ── CONVEX API ACCESSORS (DataLayer, QueryEngine) ──────────────────────────
  getConvexRef(tableName: string, op: 'list' | 'get' | 'create' | 'update' | 'delete');
  getMutationRefs(tableName: string): { create?; update?; delete? };

  // ── CACHE ACCESSORS (DataLayer, QueryEngine) ───────────────────────────────
  getStaleTime(tableName: string): number;
  getGcTime(tableName: string): number;

  // ── CONFLICT ACCESSORS (SyncEngine) ────────────────────────────────────────
  getConflictStrategy(tableName: string): ConflictStrategy;
  getMergeConfig(tableName: string): MergeConfig | undefined;
  getTableStrategies(): Record<string, ConflictStrategy>;
  getTableMergeConfigs(): Record<string, MergeConfig>;

  // ── ANALYTICS ACCESSORS (QueryEngine) ──────────────────────────────────────
  isAnalyticsEnabled(tableName: string): boolean;
  getAnalyticsFreshness(tableName: string): 'realtime' | 'near-realtime' | 'eventual';
  getAnalyticsStaleTime(tableName: string): number;
}
```

### 4.4 How Libraries Access It

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED TABLE REGISTRY                              │
│                                                                              │
│  App defines tables ONCE in DataLayerConfig                                 │
│                                                                              │
│  <DataLayerProvider config={{                                               │
│    tables: [                                                                │
│      { name: 'users', convex: {...}, staleTime: ..., conflictStrategy: ...},│
│      { name: 'orders', convex: {...}, analytics: { enabled: true } },       │
│    ],                                                                       │
│  }}>                                                                        │
│                                    │                                        │
│                                    ▼                                        │
│                   DataLayerContainer creates TableRegistry                  │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐          ┌─────────────────┐         ┌─────────────┐      │
│  │ SyncEngine  │          │  DataLayer      │         │ QueryEngine │      │
│  │             │          │  Hooks          │         │             │      │
│  │ Uses:       │          │                 │         │ Uses:       │      │
│  │ - conflict  │          │ Uses:           │         │ - convex    │      │
│  │   Strategy  │          │ - convex refs   │         │   refs      │      │
│  │ - mergeConf │          │ - staleTime     │         │ - staleTime │      │
│  │             │          │ - gcTime        │         │ - analytics │      │
│  └─────────────┘          └─────────────────┘         └─────────────┘      │
│                                                                              │
│  All access via: useDataLayerInternals().tableRegistry                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 DataLayerInternals Exposes TableRegistry

```typescript
// libs/foundation/data-layer/src/provider/data-layer-internals-context.ts

export interface DataLayerInternals {
  queryClient: QueryClient;
  convexClient: ConvexReactClient;
  convexQueryClient: ConvexQueryClient;
  database: DatabaseFacade;
  syncCoordinator: SyncCoordinator;
  duckdbRouter: DuckDBRouter | null;
  isOnline: boolean;
  cacheConfig: ResolvedCacheConfig;

  // NEW: Unified table registry (single source of truth)
  tableRegistry: TableRegistry;
}
```

### 4.6 QueryEngine Uses TableRegistry Instead of Separate Config

```typescript
// libs/foundation/query-engine/src/hooks/use-query-engine.ts

export const useQueryEngine = <TData>(options: UseQueryEngineOptions<TData>) => {
  // Get tableRegistry from data-layer (NOT from query-engine config!)
  const { tableRegistry, duckdbRouter, isOnline } = useDataLayerInternals();

  // All table metadata comes from unified registry
  const tableConfig = tableRegistry.getTable(primaryTable);
  const listRef = tableRegistry.getConvexRef(primaryTable, 'list');
  const staleTime = tableRegistry.getStaleTime(primaryTable);
  const canUseDuckDB = tableRegistry.isAnalyticsEnabled(primaryTable);
};
```

### 4.7 QueryEngineProvider Becomes Simpler

Since table metadata is in DataLayer, QueryEngineProvider only needs:

```typescript
export interface QueryEngineConfig {
  /** DataSource API for Parquet files (if using analytics) */
  readonly dataSourceApi?: FunctionReference<'query'>;

  /** Default stale time override (optional, uses DataLayer default) */
  readonly defaultStaleTime?: number;

  // NO MORE `tables` config here - it's in DataLayerConfig!
}
```

---

## 5. Type Definitions

### 5.1 Query Operations (CRUDL Only)

```typescript
// libs/foundation/query-engine/src/types/operations.ts

export const QUERY_OPERATIONS = {
  GET: 'get',
  LIST: 'list',
  CREATE: 'create',
  UPDATE: 'update',
  DELETE: 'delete',
} as const;

export type QueryOperation = (typeof QUERY_OPERATIONS)[keyof typeof QUERY_OPERATIONS];
```

### 4.2 Aggregation Types

```typescript
// libs/foundation/query-engine/src/types/aggregation.ts

export const AGGREGATIONS = {
  SUM: 'sum',
  COUNT: 'count',
  AVG: 'avg',
  MIN: 'min',
  MAX: 'max',
  COUNT_DISTINCT: 'countDistinct',
} as const;

export type Aggregation = (typeof AGGREGATIONS)[keyof typeof AGGREGATIONS];
```

### 4.3 DimensionSpec (Object-Based)

```typescript
// libs/foundation/query-engine/src/types/dimension.ts

/**
 * Object-based dimension specification.
 *
 * @example
 * { member: 'users.name' }
 * { member: 'users.name', alias: 'user_name' }
 */
export interface DimensionSpec {
  /** Member reference: 'table.column' */
  readonly member: string;

  /** Optional alias for the result */
  readonly alias?: string;
}
```

### 4.4 MeasureSpec (Object-Based)

```typescript
// libs/foundation/query-engine/src/types/measure.ts

/**
 * Object-based measure specification with aggregation.
 * Presence of measures triggers DuckDB path.
 *
 * @example
 * { member: 'orders.amount', aggregation: 'sum' }
 * { member: 'orders.amount', aggregation: 'sum', alias: 'total_revenue' }
 * { member: 'orders.id', aggregation: 'countDistinct', alias: 'unique_orders' }
 */
export interface MeasureSpec {
  /** Member reference: 'table.column' */
  readonly member: string;

  /** Aggregation function */
  readonly aggregation: Aggregation;

  /** Optional alias for the result */
  readonly alias?: string;

  /** Use DISTINCT */
  readonly distinct?: boolean;

  /** Filter for this measure only */
  readonly filter?: FilterCondition;
}
```

### 4.5 Filter Types

```typescript
// libs/foundation/query-engine/src/types/filter.ts

export const FILTER_OPERATORS = {
  EQUALS: 'equals',
  NOT_EQUALS: 'notEquals',
  CONTAINS: 'contains',
  NOT_CONTAINS: 'notContains',
  STARTS_WITH: 'startsWith',
  ENDS_WITH: 'endsWith',
  GT: 'gt',
  GTE: 'gte',
  LT: 'lt',
  LTE: 'lte',
  IN: 'in',
  NOT_IN: 'notIn',
  IS_NULL: 'isNull',
  IS_NOT_NULL: 'isNotNull',
  BETWEEN: 'between',
} as const;

export type FilterOperator = (typeof FILTER_OPERATORS)[keyof typeof FILTER_OPERATORS];

export interface FilterCondition {
  readonly member: string;
  readonly operator: FilterOperator;
  readonly values?: ReadonlyArray<unknown>;
}

export interface FilterGroup {
  readonly and?: ReadonlyArray<FilterCondition | FilterGroup>;
  readonly or?: ReadonlyArray<FilterCondition | FilterGroup>;
}

export type FilterExpression = FilterCondition | FilterGroup;
```

### 4.6 Join Types

```typescript
// libs/foundation/query-engine/src/types/join.ts

export const JOIN_TYPES = {
  INNER: 'inner',
  LEFT: 'left',
  RIGHT: 'right',
  FULL: 'full',
} as const;

export type JoinType = (typeof JOIN_TYPES)[keyof typeof JOIN_TYPES];

/**
 * Join specification. Tables inferred from left/right members.
 * Presence of joins triggers DuckDB path.
 *
 * @example
 * { left: 'orders.user_id', right: 'users.id', type: 'inner' }
 */
export interface JoinSpec {
  /** Left side: 'table.column' */
  readonly left: string;

  /** Right side: 'table.column' */
  readonly right: string;

  /** Join type */
  readonly type: JoinType;

  /** Optional alias */
  readonly alias?: string;
}
```

### 4.7 Order By

```typescript
// libs/foundation/query-engine/src/types/order.ts

export const ORDER_DIRECTIONS = {
  ASC: 'asc',
  DESC: 'desc',
} as const;

export type OrderDirection = (typeof ORDER_DIRECTIONS)[keyof typeof ORDER_DIRECTIONS];

export interface OrderBySpec {
  readonly member: string;
  readonly direction: OrderDirection;
  readonly nulls?: 'first' | 'last';
}
```

### 4.8 Enterprise Query

```typescript
// libs/foundation/query-engine/src/types/query.ts

export interface EnterpriseQuery {
  /** Operation type (default: 'list') */
  readonly operation?: QueryOperation;

  /** Dimensions (columns to select) - TABLE INFERRED FROM HERE */
  readonly dimensions?: ReadonlyArray<DimensionSpec>;

  /** Measures (aggregations) - Triggers DuckDB path */
  readonly measures?: ReadonlyArray<MeasureSpec>;

  /** Filters */
  readonly filters?: ReadonlyArray<FilterExpression>;

  /** Joins - Triggers DuckDB path */
  readonly joins?: ReadonlyArray<JoinSpec>;

  /** Order by */
  readonly orderBy?: ReadonlyArray<OrderBySpec>;

  /** Limit */
  readonly limit?: number;

  /** Offset */
  readonly offset?: number;

  /** Entity ID (for GET operation) */
  readonly entityId?: string;

  /** Data payload (for CREATE/UPDATE) */
  readonly data?: Record<string, unknown>;

  /** Enable/disable query */
  readonly enabled?: boolean;
}
```

### 4.9 Table Source & Config

```typescript
// libs/foundation/query-engine/src/types/table.ts

import type { FunctionReference } from 'convex/server';

export const TABLE_SOURCES = {
  CONVEX: 'convex',
  LOCAL: 'local',
} as const;

export type TableSource = (typeof TABLE_SOURCES)[keyof typeof TABLE_SOURCES];

export const TABLE_LOAD_STATES = {
  NOT_LOADED: 'not_loaded',
  LOADING: 'loading',
  LOADED: 'loaded',
  ERROR: 'error',
} as const;

export type TableLoadState = (typeof TABLE_LOAD_STATES)[keyof typeof TABLE_LOAD_STATES];

export const CONFLICT_STRATEGIES = {
  SERVER_WINS: 'server-wins',
  CLIENT_WINS: 'client-wins',
  LAST_WRITE_WINS: 'last-write-wins',
  MANUAL: 'manual',
  MERGE: 'merge',
} as const;

export type ConflictStrategy = (typeof CONFLICT_STRATEGIES)[keyof typeof CONFLICT_STRATEGIES];

export interface TableConvexFunctions {
  readonly list?: FunctionReference<'query'>;
  readonly get?: FunctionReference<'query'>;
  readonly create?: FunctionReference<'mutation'>;
  readonly update?: FunctionReference<'mutation'>;
  readonly delete?: FunctionReference<'mutation'>;
}

export interface ParquetFileInfo {
  readonly url: string;
  readonly filename: string;
  readonly size: number;
  readonly opfsPath?: string;
  readonly downloaded?: boolean;
}

export interface TableConfig {
  /** Table name (unique identifier) */
  readonly name: string;

  /** Source: 'convex' or 'local' */
  readonly source: TableSource;

  /** Convex API functions */
  readonly convex?: TableConvexFunctions;

  /** Loading state */
  readonly loadState: TableLoadState;

  /** Load error */
  readonly loadError?: Error;

  /** Schema */
  readonly schema?: Record<string, string>;

  /** Row count */
  readonly rowCount?: number;

  /** Parquet files */
  readonly files?: ReadonlyArray<ParquetFileInfo>;

  /** OPFS path */
  readonly opfsPath?: string;

  /** File type for local files */
  readonly fileType?: 'parquet' | 'csv' | 'json';

  /** Is user-uploaded */
  readonly isUserUploaded?: boolean;

  /** When loaded (client timestamp) */
  readonly loadedAt?: number;

  /** When backend last ingested (from API) */
  readonly lastIngestedAt?: number;

  /** Registered timestamp */
  readonly registeredAt: number;

  /** Stale time in ms (default: provider's defaultStaleTime) */
  readonly staleTime?: number;

  /** Auto-refresh when new data available */
  readonly autoRefresh?: boolean;

  /** Conflict resolution strategy */
  readonly conflictStrategy?: ConflictStrategy;
}
```

### 4.10 DataSource API Types

```typescript
// libs/foundation/query-engine/src/types/datasource.ts

export interface DataSourceFileInfo {
  readonly url: string;
  readonly filename: string;
  readonly size: number;
  readonly rowCount?: number;
}

export interface DataSourceTableInfo {
  /** Table name */
  readonly name: string;

  /** Parquet files (can be multiple, partitioned) */
  readonly files: ReadonlyArray<DataSourceFileInfo>;

  /**
   * KEY FIELD: When backend last updated this table.
   * Client compares: lastIngestedAt > loadedAt → download new files
   */
  readonly lastIngestedAt: number;

  /** Total rows */
  readonly totalRows: number;

  /** Total size */
  readonly totalSize: number;

  /** Schema */
  readonly schema: Record<string, string>;

  /** URL expiration */
  readonly expiresAt?: number;
}

export interface DataSourceResponse {
  readonly tables: ReadonlyArray<DataSourceTableInfo>;
  readonly metadata?: {
    readonly totalSize: number;
    readonly estimatedDownloadTimeMs?: number;
  };
}
```

### 4.11 Hook Result Types

```typescript
// libs/foundation/query-engine/src/types/hooks.ts

export type DataSourceType = 'api' | 'duckdb' | 'cache';

export interface UseQueryEngineResult<TData> {
  // === Data State ===
  readonly data: TData | undefined;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly isSuccess: boolean;
  readonly isError: boolean;
  readonly error: Error | null;

  // === File Loading ===
  readonly isDownloadingFiles: boolean;
  readonly downloadProgress: number;
  readonly filesToDownload: number;
  readonly filesDownloaded: number;

  // === Staleness ===
  readonly isStale: boolean;
  readonly isRevalidating: boolean;
  readonly hasNewerData: boolean;
  readonly lastUpdatedAt: number | null;

  // === Actions ===
  readonly refetch: () => Promise<void>;

  // === Metadata ===
  readonly tables: ReadonlyArray<string>;
  readonly primaryTable: string | null;
  readonly executionPath: 'api' | 'duckdb' | null;
  readonly sql: string | null;
  readonly executionTimeMs: number | null;

  // === Offline ===
  readonly isOffline: boolean;
  readonly dataSource: DataSourceType | null;
}

export interface ConflictInfo {
  readonly id: string;
  readonly table: string;
  readonly operation: 'create' | 'update' | 'delete';
  readonly localData: Record<string, unknown>;
  readonly serverData: Record<string, unknown>;
  readonly timestamp: number;
}

export interface UseMutateQueryEngineResult<TData, TVariables> {
  readonly mutate: (variables: TVariables) => Promise<TData>;
  readonly isLoading: boolean;
  readonly isSuccess: boolean;
  readonly isError: boolean;
  readonly error: Error | null;
  readonly data: TData | undefined;
  readonly reset: () => void;

  // === Offline ===
  readonly isOffline: boolean;
  readonly isPending: boolean;
  readonly pendingMutations: number;

  // === Conflicts ===
  readonly conflicts: ReadonlyArray<ConflictInfo>;
  readonly resolveConflict: (conflictId: string, resolution: 'client' | 'server' | 'merge') => void;
}
```

### 4.12 Provider Config

```typescript
// libs/foundation/query-engine/src/types/config.ts

import type { DataLayerConfig } from '@foundation/data-layer';
import type { FunctionReference } from 'convex/server';

export interface RegisterTableOptions {
  readonly name: string;
  readonly source: TableSource;
  readonly convex?: TableConvexFunctions;
  readonly fileType?: 'parquet' | 'csv' | 'json';
  readonly isUserUploaded?: boolean;
  readonly staleTime?: number;
  readonly autoRefresh?: boolean;
  readonly conflictStrategy?: ConflictStrategy;
}

export interface QueryEngineConfig {
  /** Tables to register */
  readonly tables?: ReadonlyArray<RegisterTableOptions>;

  /** DataSource API (returns Parquet URLs with lastIngestedAt) */
  readonly dataSourceApi: FunctionReference<'query'>;

  /** DataLayer config */
  readonly dataLayerConfig: DataLayerConfig;

  /** Default stale time (default: 6 hours) */
  readonly defaultStaleTime?: number;

  /** Auto-refresh on update (default: false) */
  readonly autoRefreshOnUpdate?: boolean;

  /** Background poll interval (0 = disabled) */
  readonly backgroundPollInterval?: number;
}
```

---

## 5. Decision Engine

### 5.1 Decision Flow

```
                         ┌─────────────────────┐
                         │   Incoming Query    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Extract Tables     │
                         │  from Query Members │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │      Is MUTATION?             │
                    │  (create/update/delete)       │
                    └───────────────┬───────────────┘
                                    │
                        YES         │         NO
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
         ┌─────────────────────┐     ┌─────────────────────────┐
         │     USE API         │     │      Has JOINS?         │
         │  (Always for        │     │  query.joins.length > 0 │
         │   mutations)        │     └────────────┬────────────┘
         └─────────────────────┘                  │
                                      YES         │         NO
                                  ┌───────────────┴───────────────┐
                                  │                               │
                                  ▼                               ▼
                       ┌─────────────────┐       ┌─────────────────────────┐
                       │   USE DUCKDB    │       │     Has MEASURES?       │
                       │  (Joins need    │       │ query.measures.length>0 │
                       │   SQL)          │       └────────────┬────────────┘
                       └─────────────────┘                    │
                                              YES             │         NO
                                          ┌───────────────────┴───────────────┐
                                          │                                   │
                                          ▼                                   ▼
                               ┌─────────────────┐           ┌─────────────────────────┐
                               │   USE DUCKDB    │           │    Is LOCAL table?      │
                               │  (Aggregation   │           │   source === 'local'    │
                               │   needs SQL)    │           └────────────┬────────────┘
                               └─────────────────┘                        │
                                                          YES             │         NO
                                                      ┌───────────────────┴───────────────┐
                                                      │                                   │
                                                      ▼                                   ▼
                                           ┌─────────────────┐           ┌─────────────────────────┐
                                           │   USE DUCKDB    │           │    Has LIST API?        │
                                           │  (Local files   │           │  table.convex.list      │
                                           │   only here)    │           └────────────┬────────────┘
                                           └─────────────────┘                        │
                                                                      YES             │         NO
                                                                  ┌───────────────────┴───────────────┐
                                                                  │                                   │
                                                                  ▼                                   ▼
                                                       ┌─────────────────┐           ┌─────────────────┐
                                                       │    USE API      │           │   USE DUCKDB    │
                                                       │  (Real-time     │           │  (No API, use   │
                                                       │   WebSocket)    │           │   Parquet)      │
                                                       └─────────────────┘           └─────────────────┘
```

### 5.2 Decision Rules Table

| Priority | Condition | Decision | Reason |

|----------|-----------|----------|--------|

| 1 | `operation in ['create','update','delete']` | **API** | Mutations always via API |

| 2 | `query.joins.length > 0` | **DuckDB** | Joins require SQL |

| 3 | `query.measures.length > 0` | **DuckDB** | Aggregations require SQL |

| 4 | `tables.length > 1` | **DuckDB** | Multiple tables = joins |

| 5 | `table.source === 'local'` | **DuckDB** | Local files only in DuckDB |

| 6 | `!table.convex.list` | **DuckDB** | No API available |

| 7 | Otherwise | **API** | Simple query, real-time data |

### 5.3 Decision Engine Implementation

```typescript
// libs/foundation/query-engine/src/engine/decision-engine.ts

import type { EnterpriseQuery, QueryOperation, TableConfig } from '../types';

export type ExecutionPath = 'api' | 'duckdb';

export interface DecisionResult {
  readonly path: ExecutionPath;
  readonly reason: string;
  readonly confidence: number;
  readonly apiFunction?: 'list' | 'get' | 'create' | 'update' | 'delete';
  readonly tablesToLoad?: ReadonlyArray<string>;
  readonly warnings?: ReadonlyArray<string>;
}

export interface DecisionContext {
  readonly tables: ReadonlyArray<string>;
  readonly operation: QueryOperation;
  readonly tableConfigs: ReadonlyMap<string, TableConfig>;
  readonly isOnline: boolean;
}

export class DecisionEngine {
  decide(query: EnterpriseQuery, context: DecisionContext): DecisionResult {
    const { tables, operation, tableConfigs } = context;

    // Rule 1: Mutations → API
    if (operation === 'create' || operation === 'update' || operation === 'delete') {
      const primaryTable = tables[0];
      const config = tableConfigs.get(primaryTable);

      if (!config?.convex?.[operation]) {
        return {
          path: 'api',
          reason: `No '${operation}' API defined for '${primaryTable}'`,
          confidence: 0,
          warnings: [`Cannot perform '${operation}' - no API defined`],
        };
      }

      return {
        path: 'api',
        reason: `Mutation '${operation}' uses Convex API`,
        confidence: 100,
        apiFunction: operation,
      };
    }

    // Rule 2: Has joins → DuckDB
    if (query.joins && query.joins.length > 0) {
      return {
        path: 'duckdb',
        reason: 'Query has joins - requires DuckDB',
        confidence: 100,
        tablesToLoad: [...tables],
      };
    }

    // Rule 3: Has measures → DuckDB
    if (query.measures && query.measures.length > 0) {
      return {
        path: 'duckdb',
        reason: 'Query has aggregations - requires DuckDB',
        confidence: 100,
        tablesToLoad: [...tables],
      };
    }

    // Rule 4: Multiple tables → DuckDB
    if (tables.length > 1) {
      return {
        path: 'duckdb',
        reason: 'Multiple tables - requires DuckDB',
        confidence: 100,
        tablesToLoad: [...tables],
      };
    }

    // Single table from here
    const primaryTable = tables[0];
    const config = tableConfigs.get(primaryTable);

    // Rule 5: Local table → DuckDB
    if (config?.source === 'local') {
      return {
        path: 'duckdb',
        reason: `'${primaryTable}' is local-only - requires DuckDB`,
        confidence: 100,
        tablesToLoad: [],
      };
    }

    // Rule 6: No API → DuckDB
    const hasListApi = !!config?.convex?.list;
    const hasGetApi = !!config?.convex?.get;
    const wantsGet = !!query.entityId || operation === 'get';

    if (!wantsGet && !hasListApi) {
      return {
        path: 'duckdb',
        reason: `No 'list' API for '${primaryTable}' - requires DuckDB`,
        confidence: 100,
        tablesToLoad: [primaryTable],
      };
    }

    // Rule 7: Simple query → API (real-time)
    return {
      path: 'api',
      reason: `Simple query on '${primaryTable}' - using real-time API`,
      confidence: 100,
      apiFunction: wantsGet ? 'get' : 'list',
    };
  }
}
```

---

## 6. Query Execution Paths

### 6.1 Path A: API (Simple Queries with Real-Time)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PATH A: CONVEX API (Real-Time)                          │
│                                                                              │
│  Query: {                                                                   │
│    dimensions: [{ member: 'users.name' }, { member: 'users.email' }],       │
│    filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],│
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Extract tables → ['users']                                          │
│ Step 2: Decision → API (simple query, has list API)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Use Convex's reactive useQuery (NOT convexClient.query)             │
│                                                                              │
│   // This creates a WebSocket subscription!                                 │
│   const data = useConvexQuery(api.users.list, { status: 'active' });        │
│                                                                              │
│   // When ANY user data changes on backend:                                 │
│   // → Convex pushes update via WebSocket                                   │
│   // → Component re-renders automatically                                   │
│   // → No manual refetch needed!                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Return filtered data                                                │
│                                                                              │
│   data = [                                                                  │
│     { name: 'John', email: 'john@...' },                                   │
│     { name: 'Jane', email: 'jane@...' },                                   │
│   ]                                                                          │
│                                                                              │
│   // Data auto-updates when backend changes!                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Path B: DuckDB (Complex Queries)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PATH B: DUCKDB (Analytics)                              │
│                                                                              │
│  Query: {                                                                   │
│    dimensions: [{ member: 'users.country' }],                               │
│    measures: [{ member: 'orders.amount', aggregation: 'sum', alias: 'total' }],│
│    joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],   │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Extract tables → ['users', 'orders']                                │
│ Step 2: Decision → DuckDB (has joins + measures)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Check table load state                                              │
│                                                                              │
│   'users':  loadedAt: Jan 20, staleTime: 24h → NOT STALE                   │
│   'orders': loadedAt: Jan 18, staleTime: 6h  → STALE (but usable)          │
│                                                                              │
│   → Use cached files immediately                                            │
│   → Check for updates in background (stale-while-revalidate)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: If tables not loaded, download via DataSource API                   │
│                                                                              │
│   const response = await convex.query(api.datasources.list, {              │
│     tables: ['orders']                                                       │
│   });                                                                        │
│                                                                              │
│   // Response includes lastIngestedAt                                       │
│   {                                                                          │
│     tables: [{                                                              │
│       name: 'orders',                                                       │
│       lastIngestedAt: 1705744800000,  // KEY FIELD                          │
│       files: [                                                              │
│         { url: 'https://s3.../orders_2024_01.parquet', size: 12000000 },   │
│         { url: 'https://s3.../orders_2024_02.parquet', size: 11500000 },   │
│       ],                                                                     │
│     }]                                                                       │
│   }                                                                          │
│                                                                              │
│   // Download each file → Save to OPFS → Register with DuckDB               │
│   await duckdb.execute(`                                                    │
│     CREATE OR REPLACE VIEW "orders" AS                                      │
│     SELECT * FROM read_parquet('/analytics/orders/*.parquet')              │
│   `);                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 5: Compile and execute SQL                                             │
│                                                                              │
│   SELECT                                                                    │
│     "users"."country" AS "users_country",                                   │
│     SUM("orders"."amount") AS "total"                                       │
│   FROM "orders"                                                              │
│   INNER JOIN "users" ON "orders"."user_id" = "users"."id"                   │
│   GROUP BY "users"."country"                                                │
│                                                                              │
│   const result = await duckdbRouter.query(sql);                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 6: Background revalidation (for stale tables)                          │
│                                                                              │
│   // Fire and forget                                                        │
│   revalidateInBackground(['orders']).then(({ downloaded }) => {             │
│     if (downloaded.length > 0) {                                            │
│       schemaRegistry.emit({ type: 'table-updated', ... });                 │
│       // Hook receives event → sets hasNewerData: true                      │
│     }                                                                        │
│   });                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. SchemaRegistry

```typescript
// libs/foundation/query-engine/src/registry/schema-registry.ts

import { createLogger } from '@foundation/utils';

import type { ParquetFileInfo, RegisterTableOptions, TableConfig, TableLoadState } from '../types';

const logger = createLogger('SchemaRegistry');

export type SchemaRegistryEvent =
  | { type: 'table-registered'; tableName: string; timestamp: number }
  | { type: 'table-loading'; tableName: string; timestamp: number }
  | { type: 'table-loaded'; tableName: string; timestamp: number; lastIngestedAt?: number }
  | { type: 'table-load-error'; tableName: string; error: Error; timestamp: number }
  | {
      type: 'table-updated';
      tableName: string;
      timestamp: number;
      previousLoadedAt?: number;
      newLoadedAt: number;
    }
  | { type: 'table-unregistered'; tableName: string; timestamp: number };

export type SchemaRegistryListener = (event: SchemaRegistryEvent) => void;

export class SchemaRegistry {
  private readonly tables = new Map<string, TableConfig>();
  private readonly listeners = new Set<SchemaRegistryListener>();

  registerTable(options: RegisterTableOptions): void {
    const config: TableConfig = {
      name: options.name,
      source: options.source,
      convex: options.convex,
      loadState: 'not_loaded',
      fileType: options.fileType,
      isUserUploaded: options.isUserUploaded,
      staleTime: options.staleTime,
      autoRefresh: options.autoRefresh,
      conflictStrategy: options.conflictStrategy,
      registeredAt: Date.now(),
    };

    this.tables.set(options.name, config);
    this.emit({ type: 'table-registered', tableName: options.name, timestamp: Date.now() });
    logger.info('Table registered', { name: options.name, source: options.source });
  }

  unregisterTable(name: string): boolean {
    const deleted = this.tables.delete(name);
    if (deleted) {
      this.emit({ type: 'table-unregistered', tableName: name, timestamp: Date.now() });
    }
    return deleted;
  }

  getTable(name: string): TableConfig | undefined {
    return this.tables.get(name);
  }

  hasTable(name: string): boolean {
    return this.tables.has(name);
  }

  getAllTables(): ReadonlyArray<TableConfig> {
    return Array.from(this.tables.values());
  }

  getTableNames(): ReadonlyArray<string> {
    return Array.from(this.tables.keys());
  }

  getTableLoadState(name: string): TableLoadState {
    return this.tables.get(name)?.loadState ?? 'not_loaded';
  }

  isTableStale(name: string, defaultStaleTime: number): boolean {
    const table = this.tables.get(name);
    if (!table || !table.loadedAt) return true;

    const staleTime = table.staleTime ?? defaultStaleTime;
    const age = Date.now() - table.loadedAt;
    return age > staleTime;
  }

  markTableLoading(name: string): void {
    this.updateTable(name, { loadState: 'loading', loadError: undefined });
    this.emit({ type: 'table-loading', tableName: name, timestamp: Date.now() });
  }

  markTableLoaded(
    name: string,
    info: {
      files?: ParquetFileInfo[];
      rowCount?: number;
      schema?: Record<string, string>;
      lastIngestedAt?: number;
    },
  ): void {
    this.updateTable(name, {
      loadState: 'loaded',
      loadedAt: Date.now(),
      lastIngestedAt: info.lastIngestedAt,
      files: info.files,
      rowCount: info.rowCount,
      schema: info.schema,
      loadError: undefined,
    });
    this.emit({
      type: 'table-loaded',
      tableName: name,
      timestamp: Date.now(),
      lastIngestedAt: info.lastIngestedAt,
    });
    logger.info('Table loaded', { name, rowCount: info.rowCount });
  }

  updateTableLoadedAt(name: string, lastIngestedAt: number): void {
    const table = this.tables.get(name);
    const previousLoadedAt = table?.loadedAt;

    this.updateTable(name, { loadedAt: Date.now(), lastIngestedAt });
    this.emit({
      type: 'table-updated',
      tableName: name,
      timestamp: Date.now(),
      previousLoadedAt,
      newLoadedAt: lastIngestedAt,
    });
    logger.info('Table updated', { name, lastIngestedAt: new Date(lastIngestedAt).toISOString() });
  }

  markTableLoadError(name: string, error: Error): void {
    this.updateTable(name, { loadState: 'error', loadError: error });
    this.emit({ type: 'table-load-error', tableName: name, error, timestamp: Date.now() });
    logger.error('Table load error', { name, error: error.message });
  }

  private updateTable(name: string, updates: Partial<TableConfig>): void {
    const existing = this.tables.get(name);
    if (existing) {
      this.tables.set(name, { ...existing, ...updates });
    }
  }

  private emit(event: SchemaRegistryEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (error) {
        logger.error('Event listener error', { error });
      }
    }
  }

  subscribe(listener: SchemaRegistryListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}
```

---

## 8. Parquet File Management

### 8.1 Stale-While-Revalidate Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STALE-WHILE-REVALIDATE FLOW                             │
│                                                                              │
│  1. Query comes in (DuckDB path)                                            │
│  2. Check OPFS: Have cached files?                                          │
│     ├─ YES, not stale → Execute immediately, done                           │
│     ├─ YES, stale → Execute immediately + revalidate in background          │
│     └─ NO → Download files, then execute                                    │
│                                                                              │
│  3. Background revalidation:                                                │
│     a. Call api.datasources.list({ tables: [...] })                         │
│     b. Compare: lastIngestedAt > loadedAt?                                  │
│        ├─ YES → Download new files silently                                 │
│        └─ NO → Skip download, files are current                             │
│     c. If downloaded → emit 'table-updated' event                           │
│     d. Hook receives event → sets hasNewerData: true                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 FileManager Implementation

```typescript
// libs/foundation/query-engine/src/files/file-manager.ts

import type { AnalyticsOpfsManager, DuckDBRouter } from '@foundation/bridge';
import { createLogger, Mutex } from '@foundation/utils';

import type { SchemaRegistry } from '../registry/schema-registry';
import type { DataSourceResponse, DataSourceTableInfo, ParquetFileInfo } from '../types';

const logger = createLogger('FileManager');

export interface DownloadProgress {
  readonly table: string;
  readonly totalFiles: number;
  readonly downloadedFiles: number;
  readonly totalBytes: number;
  readonly downloadedBytes: number;
  readonly percent: number;
}

export type DownloadProgressHandler = (progress: DownloadProgress) => void;

export class FileManager {
  private readonly schemaRegistry: SchemaRegistry;
  private readonly duckdbRouter: DuckDBRouter | null;
  private readonly opfsManager: AnalyticsOpfsManager | null;
  private readonly downloadingTables = new Set<string>();

  constructor(deps: {
    schemaRegistry: SchemaRegistry;
    duckdbRouter: DuckDBRouter | null;
    opfsManager: AnalyticsOpfsManager | null;
  }) {
    this.schemaRegistry = deps.schemaRegistry;
    this.duckdbRouter = deps.duckdbRouter;
    this.opfsManager = deps.opfsManager;
  }

  async downloadFiles(
    response: DataSourceResponse,
    onProgress?: DownloadProgressHandler,
  ): Promise<void> {
    if (!this.opfsManager || !this.duckdbRouter) {
      throw new Error('OPFS or DuckDB not available');
    }

    for (const tableInfo of response.tables) {
      const { name: tableName, files, totalRows, schema, lastIngestedAt } = tableInfo;

      if (this.downloadingTables.has(tableName)) {
        logger.debug('Table already downloading', { tableName });
        continue;
      }

      this.downloadingTables.add(tableName);
      this.schemaRegistry.markTableLoading(tableName);

      try {
        const downloadedFiles: ParquetFileInfo[] = [];
        let downloadedBytes = 0;
        const totalBytes = files.reduce((sum, f) => sum + f.size, 0);

        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          const fetchResponse = await fetch(file.url);

          if (!fetchResponse.ok) {
            throw new Error(`Failed to download ${file.filename}: ${fetchResponse.status}`);
          }

          const arrayBuffer = await fetchResponse.arrayBuffer();
          downloadedBytes += arrayBuffer.byteLength;

          const opfsPath = `/analytics/${tableName}/${file.filename}`;
          await this.opfsManager.writeFile(opfsPath, new Uint8Array(arrayBuffer), {
            tableName,
            fileType: 'parquet',
          });

          downloadedFiles.push({
            url: file.url,
            filename: file.filename,
            size: file.size,
            opfsPath,
            downloaded: true,
          });

          if (onProgress) {
            onProgress({
              table: tableName,
              totalFiles: files.length,
              downloadedFiles: i + 1,
              totalBytes,
              downloadedBytes,
              percent: Math.round((downloadedBytes / totalBytes) * 100),
            });
          }
        }

        // Register with DuckDB
        await this.registerTableWithDuckDB(tableName);

        this.schemaRegistry.markTableLoaded(tableName, {
          files: downloadedFiles,
          rowCount: totalRows,
          schema,
          lastIngestedAt,
        });

        logger.info('Table downloaded', { tableName, fileCount: files.length });
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error));
        this.schemaRegistry.markTableLoadError(tableName, err);
        throw err;
      } finally {
        this.downloadingTables.delete(tableName);
      }
    }
  }

  /**
   * KEY METHOD: Compare lastIngestedAt and download only if newer
   */
  async downloadIfNewer(
    response: DataSourceResponse,
    onProgress?: DownloadProgressHandler,
  ): Promise<{ downloaded: string[]; skipped: string[] }> {
    const downloaded: string[] = [];
    const skipped: string[] = [];

    for (const tableInfo of response.tables) {
      const { name: tableName, lastIngestedAt } = tableInfo;

      const cachedTable = this.schemaRegistry.getTable(tableName);
      const cachedLastIngestedAt = cachedTable?.lastIngestedAt ?? 0;

      // KEY COMPARISON
      const needsDownload = lastIngestedAt > cachedLastIngestedAt;

      if (needsDownload) {
        logger.info('Newer data available', {
          tableName,
          cached: new Date(cachedLastIngestedAt).toISOString(),
          server: new Date(lastIngestedAt).toISOString(),
        });

        await this.downloadFiles({ tables: [tableInfo], metadata: response.metadata }, onProgress);
        downloaded.push(tableName);
      } else {
        logger.debug('Files up-to-date', { tableName });
        skipped.push(tableName);
      }
    }

    return { downloaded, skipped };
  }

  async registerTableWithDuckDB(tableName: string): Promise<void> {
    if (!this.duckdbRouter) {
      throw new Error('DuckDB not available');
    }

    const sql = `
      CREATE OR REPLACE VIEW "${tableName}" AS
      SELECT * FROM read_parquet('/analytics/${tableName}/*.parquet')
    `;

    await this.duckdbRouter.execute(sql);
    logger.debug('DuckDB view created', { tableName });
  }

  async saveLocalFile(
    tableName: string,
    file: File,
    fileType: 'parquet' | 'csv' | 'json',
  ): Promise<{ opfsPath: string; schema: Record<string, string> }> {
    if (!this.opfsManager || !this.duckdbRouter) {
      throw new Error('OPFS or DuckDB not available');
    }

    const arrayBuffer = await file.arrayBuffer();
    const opfsPath = `/local/${tableName}.${fileType}`;

    await this.opfsManager.writeFile(opfsPath, new Uint8Array(arrayBuffer), {
      tableName,
      fileType,
      source: 'local',
    });

    // Register with DuckDB based on file type
    let sql: string;
    switch (fileType) {
      case 'parquet':
        sql = `CREATE OR REPLACE VIEW "${tableName}" AS SELECT * FROM read_parquet('${opfsPath}')`;
        break;
      case 'csv':
        sql = `CREATE OR REPLACE VIEW "${tableName}" AS SELECT * FROM read_csv_auto('${opfsPath}')`;
        break;
      case 'json':
        sql = `CREATE OR REPLACE VIEW "${tableName}" AS SELECT * FROM read_json_auto('${opfsPath}')`;
        break;
    }

    await this.duckdbRouter.execute(sql);

    // Infer schema
    const schemaResult = await this.duckdbRouter.query(
      `DESCRIBE SELECT * FROM "${tableName}" LIMIT 1`,
    );
    const schema: Record<string, string> = {};
    for (const row of schemaResult as Array<{ column_name: string; column_type: string }>) {
      schema[row.column_name] = row.column_type;
    }

    // Register in SchemaRegistry
    this.schemaRegistry.registerTable({
      name: tableName,
      source: 'local',
      fileType,
      isUserUploaded: true,
    });

    this.schemaRegistry.markTableLoaded(tableName, { schema });

    return { opfsPath, schema };
  }
}
```

---

## 9. Real-Time Updates (Leveraging foundation-data-layer)

### 9.1 Reusing Existing Infrastructure

**IMPORTANT:** The Convex + TanStack Query integration is **already implemented** in `foundation-data-layer`. We do NOT recreate it - we reuse it via `useDataLayerInternals()`.

Reference: https://docs.convex.dev/client/tanstack/tanstack-query/

### 9.2 What foundation-data-layer Already Provides

```typescript
// From useDataLayerInternals() hook:
interface DataLayerInternals {
  queryClient: QueryClient; // TanStack Query client (already wired to Convex)
  convexClient: ConvexReactClient; // Convex React client
  convexQueryClient: ConvexQueryClient; // Convex Query client (for reactive subscriptions)
  database: DatabaseFacade; // IndexedDB cache
  syncCoordinator: SyncCoordinator; // Offline sync from sync-engine
  duckdbRouter: DuckDBRouter | null; // DuckDB from bridge
  isOnline: boolean; // Network status
  cacheConfig: ResolvedCacheConfig; // Cache settings
}
```

**Already configured in DataLayerContainer:**

- `ConvexQueryClient` created and connected to `QueryClient`
- `queryKeyHashFn` and `queryFn` from `convexQueryClient`
- Offline-first defaults, retry logic, stale/gc times
- Provider hierarchy: `ConvexProvider` → `QueryClientProvider`

### 9.3 How Query Engine Uses It

```typescript
// libs/foundation/query-engine/src/hooks/use-query-engine.ts

import { convexQuery } from '@convex-dev/react-query';
import { useDataLayerInternals } from '@foundation/data-layer';
import { useQuery } from '@tanstack/react-query';

export const useQueryEngine = <TData>(options: UseQueryEngineOptions<TData>) => {
  // Get everything from data-layer - NO need to create new clients!
  const {
    convexQueryClient, // Already wired to QueryClient
    duckdbRouter, // For DuckDB queries
    syncCoordinator, // For offline mutations
    isOnline,
  } = useDataLayerInternals();

  // For API path: use convexQuery() which creates reactive subscription
  if (decision.path === 'api') {
    // convexQuery() creates TanStack Query options with:
    // - WebSocket subscription for real-time updates
    // - Automatic cache updates when data changes
    // - isStale is ALWAYS false
    const result = useQuery({
      ...convexQuery(apiRef, apiArgs),
      // Can spread additional options
      gcTime: 10000, // Stay subscribed 10s after unmount
    });
    return result;
  }

  // For DuckDB path: use regular useQuery
  // (no real-time, use stale-while-revalidate)
};
```

### 9.4 Key Differences from Regular TanStack Query

| Aspect | Regular TanStack Query | Convex via convexQuery() |

|--------|----------------------|-------------------------|

| Update mechanism | Polling / manual refetch | WebSocket push |

| `isStale` | Can be true | **Always false** |

| Retry options | Configurable | Handled by Convex WebSocket |

| Refetch options | Needed | **Not needed** (always up to date) |

| `gcTime` | Cache lifetime | Subscription lifetime after unmount |

### 9.5 Real-Time vs Stale-While-Revalidate

| Aspect | API Path (Real-Time) | DuckDB Path (Stale-While-Revalidate) |

|--------|---------------------|-------------------------------------|

| **Data source** | Convex backend | Local Parquet files |

| **Update mechanism** | WebSocket push | Background polling + `lastIngestedAt` |

| **Latency** | Instant | Depends on staleTime config |

| **User action needed** | None | Optional (can auto-refresh or show banner) |

---

## 10. Sync Engine Integration

### 10.1 Components Used

| Component | Purpose |

|-----------|---------|

| **OfflineQueue** | Queue mutations when offline, persist to IndexedDB |

| **SyncCoordinator** | Process queue when online, manage retries |

| **ConflictResolver** | Detect and resolve conflicts with configurable strategy |

| **CrossTabManager** | Sync state across browser tabs via BroadcastChannel |

| **OptimisticUpdater** | Apply changes to cache immediately |

| **RollbackManager** | Revert changes on server failure |

### 10.2 Mutation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MUTATION FLOW                                       │
│                                                                              │
│  User: mutate({ operation: 'create', data: {...} })                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: OPTIMISTIC UPDATE (Immediate)                                       │
│                                                                              │
│   optimisticUpdater.apply({                                                 │
│     optimisticId: 'temp-123',                                               │
│     operation: 'create',                                                    │
│     data: { id: 'temp-123', ...userData, _pending: true },                 │
│     previousState: currentCacheState,                                       │
│   });                                                                        │
│                                                                              │
│   // TanStack Query cache updated immediately                               │
│   // UI shows new item with _pending: true                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: BROADCAST TO OTHER TABS                                             │
│                                                                              │
│   crossTabManager.broadcast({                                               │
│     type: 'mutation-applied',                                               │
│     table: 'users',                                                         │
│     operation: 'create',                                                    │
│     data: { id: 'temp-123', ... },                                         │
│   });                                                                        │
│                                                                              │
│   // All other browser tabs receive this and update their cache             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                        ┌───────────┴───────────┐
                        │                       │
                     ONLINE                  OFFLINE
                        │                       │
                        ▼                       ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│ Step 3a: SEND TO SERVER       │ │ Step 3b: QUEUE MUTATION       │
│                               │ │                               │
│ await convex.mutation(        │ │ await offlineQueue.enqueue({  │
│   api.users.create,           │ │   id: 'temp-123',             │
│   userData                    │ │   operation: 'create',        │
│ );                            │ │   table: 'users',             │
│                               │ │   data: userData,             │
│                               │ │   previousState: ...,         │
│                               │ │ });                           │
│                               │ │                               │
│                               │ │ // Persisted to IndexedDB     │
│                               │ │ // isPending: true in UI      │
└───────────────────────────────┘ └───────────────────────────────┘
            │                                   │
    ┌───────┴───────┐                           │
    │               │                           │
 SUCCESS         FAILURE                        │
    │               │                           │
    ▼               ▼                           │
┌───────────┐ ┌───────────────────┐             │
│ CONFIRM   │ │ ROLLBACK          │             │
│           │ │                   │             │
│ Replace   │ │ rollbackManager   │             │
│ temp-123  │ │   .revert(...)    │             │
│ with real │ │                   │             │
│ server ID │ │ // UI reverts     │             │
│           │ │ // Show error     │             │
└───────────┘ └───────────────────┘             │
                                                │
                                                ▼ (When back online)
                                   ┌───────────────────────────────┐
                                   │ SYNC COORDINATOR              │
                                   │                               │
                                   │ syncCoordinator               │
                                   │   .processOfflineQueue();     │
                                   │                               │
                                   │ // For each queued mutation:  │
                                   │ // 1. Send to server          │
                                   │ // 2. On success → confirm    │
                                   │ // 3. On failure → rollback   │
                                   │ // 4. On conflict → resolve   │
                                   └───────────────────────────────┘
```

### 10.3 Conflict Resolution

```typescript
// Per-table conflict strategy configuration
<QueryEngineProvider
  config={{
    tables: [
      {
        name: 'orders',
        conflictStrategy: 'last-write-wins', // Compare timestamps
      },
      {
        name: 'user_preferences',
        conflictStrategy: 'client-wins', // Always use client data
      },
      {
        name: 'inventory',
        conflictStrategy: 'server-wins', // Always use server data
      },
      {
        name: 'documents',
        conflictStrategy: 'manual', // Show UI to user
      },
    ],
  }}
/>;

// In hook
const { conflicts, resolveConflict } = useMutateQueryEngine();

if (conflicts.length > 0) {
  return (
    <ConflictDialog conflicts={conflicts} onResolve={(id, choice) => resolveConflict(id, choice)} />
  );
}
```

---

## 11. Hooks Implementation

### 11.1 useQueryEngine

```typescript
// libs/foundation/query-engine/src/hooks/use-query-engine.ts

import { useCallback, useEffect, useMemo, useState } from 'react';

import { convexQuery } from '@convex-dev/react-query'; // Official helper!

import { useDataLayerInternals } from '@foundation/data-layer';
import { hashPayloadSync } from '@foundation/utils';
import { useQuery } from '@tanstack/react-query';

import { useQueryEngineContext } from '../context/query-engine-context';
import type { EnterpriseQuery, QueryOperation, UseQueryEngineResult } from '../types';

export interface UseQueryEngineOptions<TData = unknown> {
  readonly query: EnterpriseQuery;
  readonly operation?: QueryOperation;
  readonly enabled?: boolean;
  readonly staleTime?: number;
  readonly gcTime?: number; // For Convex subscriptions
  readonly select?: (data: unknown) => TData;
}

export const useQueryEngine = <TData = unknown>(
  options: UseQueryEngineOptions<TData>,
): UseQueryEngineResult<TData> => {
  const { query, operation = 'list', enabled = true, staleTime, gcTime, select } = options;

  // Get from data-layer (already wired up!)
  const { syncCoordinator, isOnline } = useDataLayerInternals();

  // Get from query-engine context
  const {
    orchestrator,
    schemaRegistry,
    defaultStaleTime,
    decisionEngine,
    tableExtractor,
    apiExecutor,
  } = useQueryEngineContext();

  // State for file downloads (DuckDB path only)
  const [downloadState, setDownloadState] = useState({
    isDownloadingFiles: false,
    downloadProgress: 0,
    filesToDownload: 0,
    filesDownloaded: 0,
  });
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [hasNewerData, setHasNewerData] = useState(false);

  // Extract tables and make routing decision
  const tables = useMemo(() => tableExtractor.extract(query), [query, tableExtractor]);
  const primaryTable = tables[0] ?? null;

  const decision = useMemo(() => {
    if (!primaryTable || !enabled) return null;

    const tableConfigs = new Map(tables.map((name) => [name, schemaRegistry.getTable(name)!]));

    return decisionEngine.decide(query, {
      tables,
      operation,
      tableConfigs,
      isOnline,
    });
  }, [query, tables, operation, primaryTable, enabled, schemaRegistry, decisionEngine, isOnline]);

  const isApiPath = decision?.path === 'api';

  // For API path: get the Convex function reference
  const apiRef = useMemo(() => {
    if (!isApiPath || !primaryTable) return null;
    const tableConfig = schemaRegistry.getTable(primaryTable);
    return tableConfig?.convex?.[decision?.apiFunction ?? 'list'] ?? null;
  }, [isApiPath, primaryTable, decision, schemaRegistry]);

  // Convert filters to API args
  const apiArgs = useMemo(() => {
    if (!isApiPath || !query.filters) return {};
    return apiExecutor.filtersToArgs(query.filters);
  }, [isApiPath, query.filters, apiExecutor]);

  // =========================================================================
  // API PATH: Use convexQuery() for reactive WebSocket subscription
  // Reference: https://docs.convex.dev/client/tanstack/tanstack-query/
  // =========================================================================
  const apiResult = useQuery({
    // convexQuery() creates TanStack Query options with:
    // - Reactive WebSocket subscription
    // - Auto-updates when data changes (no polling!)
    // - isStale is ALWAYS false
    ...convexQuery(apiRef!, apiArgs),

    // Additional options
    enabled: enabled && isApiPath && apiRef !== null,
    gcTime: gcTime ?? 5 * 60 * 1000, // Stay subscribed 5 min after unmount

    // select can transform data
    select: select ? (data: unknown) => select(data) as TData : undefined,
  });

  // =========================================================================
  // DUCKDB PATH: Use regular TanStack Query with orchestrator
  // Uses stale-while-revalidate (not real-time)
  // =========================================================================
  const queryKey = useMemo(
    () => ['query-engine', 'duckdb', hashPayloadSync(query), operation],
    [query, operation],
  );

  const duckdbResult = useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      setIsRevalidating(true);

      const result = await orchestrator.execute({
        query,
        operation,
        signal,
        onDownloadProgress: (progress) => {
          setDownloadState({
            isDownloadingFiles: true,
            downloadProgress: progress.percent,
            filesToDownload: progress.totalFiles,
            filesDownloaded: progress.downloadedFiles,
          });
        },
      });

      setDownloadState((prev) => ({ ...prev, isDownloadingFiles: false }));
      setIsRevalidating(result.revalidateInBackground);
      setHasNewerData(false);

      return result;
    },
    enabled: enabled && !isApiPath,
    staleTime: staleTime ?? defaultStaleTime,
  });

  // Subscribe to table updates (for DuckDB path - stale-while-revalidate)
  useEffect(() => {
    if (isApiPath) return; // Not needed for API path (Convex handles it)

    const unsubscribe = schemaRegistry.subscribe((event) => {
      if (event.type === 'table-updated' && tables.includes(event.tableName)) {
        setHasNewerData(true);
        setIsRevalidating(false);
      }
    });
    return unsubscribe;
  }, [schemaRegistry, tables, isApiPath]);

  // Subscribe to cross-tab updates via sync coordinator
  useEffect(() => {
    if (isApiPath) return; // Convex handles cross-tab for API path

    const unsubscribe = syncCoordinator.subscribe((event) => {
      if (event.type === 'mutation-synced' && tables.includes(event.table)) {
        setHasNewerData(true);
      }
    });
    return unsubscribe;
  }, [syncCoordinator, tables, isApiPath]);

  // Combine results based on execution path
  const data = useMemo(() => {
    if (isApiPath) {
      return apiResult.data as TData | undefined;
    }
    const rawData = duckdbResult.data?.data;
    return (select ? select(rawData) : rawData) as TData | undefined;
  }, [isApiPath, apiResult.data, duckdbResult.data, select]);

  const isLoading = isApiPath ? apiResult.isLoading : duckdbResult.isLoading;
  const isFetching = isApiPath ? apiResult.isFetching : duckdbResult.isFetching;

  const handleRefetch = useCallback(async () => {
    setHasNewerData(false);
    if (isApiPath) {
      await apiResult.refetch();
    } else {
      await duckdbResult.refetch();
    }
  }, [isApiPath, apiResult, duckdbResult]);

  return {
    data,
    isLoading,
    isFetching,
    isSuccess: isApiPath ? apiResult.isSuccess : duckdbResult.isSuccess,
    isError: isApiPath ? apiResult.isError : duckdbResult.isError,
    error: isApiPath ? (apiResult.error as Error | null) : (duckdbResult.error as Error | null),
    ...downloadState,
    // API path: isStale is ALWAYS false (Convex data is always fresh)
    isStale: isApiPath ? false : duckdbResult.data?.isStale ?? false,
    isRevalidating,
    hasNewerData,
    lastUpdatedAt: isApiPath ? apiResult.dataUpdatedAt ?? null : duckdbResult.dataUpdatedAt ?? null,
    refetch: handleRefetch,
    tables,
    primaryTable,
    executionPath: decision?.path ?? null,
    sql: isApiPath ? null : duckdbResult.data?.sql ?? null,
    executionTimeMs: isApiPath ? null : duckdbResult.data?.executionTimeMs ?? null,
    isOffline: !isOnline,
    dataSource: decision?.path ?? null,
  };
};
```

### 11.2 useMutateQueryEngine

```typescript
// libs/foundation/query-engine/src/hooks/use-mutate-query-engine.ts

import { useCallback, useEffect, useMemo, useState } from 'react';

import { useConvexMutation } from '@convex-dev/react-query'; // Official helper!

import { useDataLayerInternals } from '@foundation/data-layer';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { useQueryEngineContext } from '../context/query-engine-context';
import type { ConflictInfo, EnterpriseQuery, UseMutateQueryEngineResult } from '../types';

export interface MutationVariables {
  readonly operation: 'create' | 'update' | 'delete';
  readonly dimensions: EnterpriseQuery['dimensions'];
  readonly data?: Record<string, unknown>;
  readonly entityId?: string;
  readonly filters?: EnterpriseQuery['filters'];
}

export const useMutateQueryEngine = <TData = unknown>(): UseMutateQueryEngineResult<
  TData,
  MutationVariables
> => {
  // Get from data-layer
  const { queryClient, syncCoordinator, isOnline } = useDataLayerInternals();

  // Get from query-engine context
  const { schemaRegistry, tableExtractor, optimisticUpdater, rollbackManager } =
    useQueryEngineContext();

  const [pendingMutations, setPendingMutations] = useState(0);
  const [conflicts, setConflicts] = useState<ConflictInfo[]>([]);

  // Subscribe to sync events for offline mutation processing
  useEffect(() => {
    const unsubscribe = syncCoordinator.subscribe((event) => {
      switch (event.type) {
        case 'mutation-synced':
          // Offline mutation was synced successfully
          optimisticUpdater.confirm(event.optimisticId, event.serverId, event.serverData);
          setPendingMutations((prev) => Math.max(0, prev - 1));
          break;

        case 'mutation-failed':
          // Offline mutation failed during sync
          rollbackManager.revert(event.optimisticId, event.previousState);
          setPendingMutations((prev) => Math.max(0, prev - 1));
          break;

        case 'conflict-detected':
          // Conflict detected during sync - check strategy
          const tableConfig = schemaRegistry.getTable(event.table);
          const strategy = tableConfig?.conflictStrategy ?? 'server-wins';

          if (strategy === 'manual') {
            // Manual resolution - add to conflicts array
            setConflicts((prev) => [...prev, event.conflict as ConflictInfo]);
          }
          // Other strategies are handled automatically by sync coordinator
          break;

        case 'queue-processed':
          setPendingMutations(0);
          break;
      }
    });

    return unsubscribe;
  }, [syncCoordinator, optimisticUpdater, rollbackManager, schemaRegistry]);

  const mutation = useMutation({
    mutationFn: async (variables: MutationVariables) => {
      const { operation, dimensions, data, entityId, filters } = variables;

      // Extract table from query members
      const tables = tableExtractor.extract({ dimensions, filters });
      const primaryTable = tables[0];

      if (!primaryTable) {
        throw new Error('Could not extract table from mutation');
      }

      // Get table config
      const tableConfig = schemaRegistry.getTable(primaryTable);
      if (!tableConfig) {
        throw new Error(`Table '${primaryTable}' not registered`);
      }

      // Get mutation function reference
      const mutationRef = tableConfig.convex?.[operation];
      if (!mutationRef) {
        throw new Error(`No '${operation}' API defined for table '${primaryTable}'`);
      }

      // Generate optimistic ID
      const optimisticId = `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const previousState = queryClient.getQueryData(['query-engine', primaryTable]);

      // Step 1: Apply optimistic update immediately
      optimisticUpdater.apply({
        optimisticId,
        operation,
        table: primaryTable,
        data: { ...data, id: optimisticId, _pending: true },
        previousState,
      });

      // Step 2: Check online status
      if (!isOnline) {
        // Queue for offline processing
        await syncCoordinator.queueMutation({
          id: optimisticId,
          operation,
          table: primaryTable,
          mutationRef,
          data,
          entityId,
          previousState,
          timestamp: Date.now(),
        });

        setPendingMutations((prev) => prev + 1);

        return {
          id: optimisticId,
          _pending: true,
          _offline: true,
          ...data,
        } as unknown as TData;
      }

      // Step 3: Execute mutation via Convex
      // useConvexMutation is a re-export of useMutation from convex/react
      try {
        // Build mutation args based on operation
        let mutationArgs: Record<string, unknown>;
        switch (operation) {
          case 'create':
            mutationArgs = data ?? {};
            break;
          case 'update':
            mutationArgs = { id: entityId, ...data };
            break;
          case 'delete':
            mutationArgs = { id: entityId };
            break;
        }

        // Execute the Convex mutation
        // Note: In actual implementation, we'd use the convex client directly
        // since useConvexMutation must be at component level
        const result = await (mutationRef as any)(mutationArgs);

        // Confirm optimistic update
        const serverId = result?.id ?? result?._id ?? entityId;
        optimisticUpdater.confirm(optimisticId, serverId, result);

        // Invalidate related queries (Convex WebSocket will push updates anyway,
        // but this ensures DuckDB path queries also refresh)
        await queryClient.invalidateQueries({
          predicate: (query) => {
            const key = query.queryKey;
            return (key as unknown[]).some(
              (k) => typeof k === 'string' && k.includes(primaryTable),
            );
          },
        });

        return result as TData;
      } catch (error) {
        // Rollback on failure
        rollbackManager.revert(optimisticId, previousState);
        throw error;
      }
    },
  });

  const handleReset = useCallback(() => {
    mutation.reset();
    setPendingMutations(0);
    setConflicts([]);
  }, [mutation]);

  const handleResolveConflict = useCallback(
    (conflictId: string, resolution: 'client' | 'server' | 'merge') => {
      syncCoordinator.resolveConflict(conflictId, resolution);
      setConflicts((prev) => prev.filter((c) => c.id !== conflictId));
    },
    [syncCoordinator],
  );

  return {
    mutate: mutation.mutateAsync,
    isLoading: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error as Error | null,
    data: mutation.data,
    reset: handleReset,
    isOffline: !isOnline,
    isPending: pendingMutations > 0,
    pendingMutations,
    conflicts,
    resolveConflict: handleResolveConflict,
  };
};
```

### 11.2.1 Note on Convex Mutations

Per the official docs (https://docs.convex.dev/client/tanstack/tanstack-query/):

```typescript
// For mutations, use useConvexMutation with TanStack's useMutation
import { useConvexMutation } from '@convex-dev/react-query';
import { useMutation } from '@tanstack/react-query';

import { api } from '../convex/_generated/api';

// useConvexMutation is just a re-export of useMutation from convex/react
const { mutate, isPending } = useMutation({
  mutationFn: useConvexMutation(api.functions.doSomething),
});
```

In our implementation, we handle the mutation execution inside the `useMutation` hook to support:

- Optimistic updates
- Offline queueing via sync-engine
- Conflict resolution
- Cross-tab sync

### 11.3 useUploadFile

```typescript
// libs/foundation/query-engine/src/hooks/use-upload-file.ts

import { useCallback, useState } from 'react';

import { useQueryEngineContext } from '../context/query-engine-context';

export interface UseUploadFileOptions {
  readonly tableName: string;
  readonly fileType?: 'parquet' | 'csv' | 'json';
}

export interface UseUploadFileResult {
  readonly upload: (file: File) => Promise<void>;
  readonly isUploading: boolean;
  readonly progress: number;
  readonly error: Error | null;
  readonly schema: Record<string, string> | null;
  readonly reset: () => void;
}

const inferFileType = (filename: string): 'parquet' | 'csv' | 'json' => {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'parquet':
      return 'parquet';
    case 'json':
      return 'json';
    default:
      return 'csv';
  }
};

export const useUploadFile = (options: UseUploadFileOptions): UseUploadFileResult => {
  const { tableName, fileType: defaultFileType } = options;
  const { fileManager } = useQueryEngineContext();

  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const [schema, setSchema] = useState<Record<string, string> | null>(null);

  const handleUpload = useCallback(
    async (file: File) => {
      setIsUploading(true);
      setProgress(0);
      setError(null);
      setSchema(null);

      try {
        const fileType = defaultFileType ?? inferFileType(file.name);
        setProgress(25);

        const result = await fileManager.saveLocalFile(tableName, file, fileType);

        setProgress(100);
        setSchema(result.schema);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsUploading(false);
      }
    },
    [tableName, defaultFileType, fileManager],
  );

  const handleReset = useCallback(() => {
    setIsUploading(false);
    setProgress(0);
    setError(null);
    setSchema(null);
  }, []);

  return {
    upload: handleUpload,
    isUploading,
    progress,
    error,
    schema,
    reset: handleReset,
  };
};
```

---

## 12. Provider Implementation

### 12.1 Leveraging Existing Infrastructure

**Key Insight:** Query Engine does NOT create its own Convex/TanStack Query providers. It sits inside the `DataLayerProvider` and accesses everything via `useDataLayerInternals()`.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROVIDER HIERARCHY                                  │
│                                                                              │
│  <DataLayerProvider>                    ← From foundation-data-layer        │
│    │                                                                         │
│    ├─ ConvexProvider (client={convexClient})                                │
│    │                                                                         │
│    ├─ QueryClientProvider (client={queryClient})                            │
│    │   │                                                                     │
│    │   ├─ convexQueryClient already connected!                              │
│    │   │                                                                     │
│    │   └─ <QueryEngineProvider>         ← Our provider (thin wrapper)       │
│    │       │                                                                 │
│    │       └─ Uses useDataLayerInternals() to access:                       │
│    │           - queryClient                                                 │
│    │           - convexClient                                                │
│    │           - convexQueryClient                                           │
│    │           - duckdbRouter                                                │
│    │           - syncCoordinator                                             │
│    │           - database                                                    │
│    │                                                                         │
│    └─ SyncEngine, OfflineQueue, etc. already set up                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 QueryEngineProvider Implementation

```typescript
// libs/foundation/query-engine/src/hooks/context/query-engine-provider.tsx

import React, { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react';

import { useDataLayerInternals } from '@foundation/data-layer';
import { createLogger } from '@foundation/utils';

import { SqlCompiler } from '../../compiler/sql-compiler';
// Import existing components from query-engine
import { DecisionEngine } from '../../decision/decision-engine';
import { ApiExecutor } from '../../engine/api-executor';
import { QueryOrchestrator } from '../../engine/query-orchestrator';
// New components for enterprise features
import { TableExtractor } from '../../engine/table-extractor';
import { FileManager } from '../../files/file-manager';
import { SchemaRegistry } from '../../schema/registry';
import { OptimisticUpdater } from '../../sync/optimistic-updater';
import { RollbackManager } from '../../sync/rollback-manager';
import type { QueryEngineConfig, RegisterTableOptions } from '../../types';

const logger = createLogger('QueryEngineProvider');

const DEFAULT_STALE_TIME = 6 * 60 * 60 * 1000; // 6 hours

interface QueryEngineContextValue {
  // Core components (already exist in query-engine)
  readonly decisionEngine: DecisionEngine;
  readonly sqlCompiler: SqlCompiler;
  readonly schemaRegistry: SchemaRegistry;

  // New enterprise components
  readonly tableExtractor: TableExtractor;
  readonly fileManager: FileManager;
  readonly apiExecutor: ApiExecutor;
  readonly orchestrator: QueryOrchestrator;
  readonly optimisticUpdater: OptimisticUpdater;
  readonly rollbackManager: RollbackManager;

  // Config
  readonly defaultStaleTime: number;
  readonly dataSourceApi: QueryEngineConfig['dataSourceApi'];

  // From data-layer (pass through for convenience)
  readonly isOnline: boolean;
}

const QueryEngineContext = createContext<QueryEngineContextValue | null>(null);

export const useQueryEngineContext = (): QueryEngineContextValue => {
  const context = useContext(QueryEngineContext);
  if (!context) {
    throw new Error('useQueryEngineContext must be used within QueryEngineProvider');
  }
  return context;
};

interface QueryEngineProviderProps {
  readonly config: QueryEngineConfig;
  readonly children: ReactNode;
}

export const QueryEngineProvider: React.FC<QueryEngineProviderProps> = ({ config, children }) => {
  // Get EVERYTHING from data-layer - no need to create new clients!
  const {
    queryClient,
    convexClient,
    convexQueryClient,
    duckdbRouter,
    database,
    syncCoordinator,
    isOnline,
    cacheConfig,
  } = useDataLayerInternals();

  const defaultStaleTime = config.defaultStaleTime ?? DEFAULT_STALE_TIME;

  const contextValue = useMemo(() => {
    // 1. Schema Registry (can use existing or create new)
    const schemaRegistry = new SchemaRegistry();

    // Register tables from config
    for (const table of config.tables ?? []) {
      schemaRegistry.registerTable(table);
    }

    // 2. Decision Engine (already exists in query-engine)
    const decisionEngine = new DecisionEngine();

    // 3. SQL Compiler (already exists in query-engine)
    const sqlCompiler = new SqlCompiler();

    // 4. Table Extractor (new)
    const tableExtractor = new TableExtractor();

    // 5. File Manager - uses duckdbRouter from data-layer
    const fileManager = new FileManager({
      schemaRegistry,
      duckdbRouter,
      // opfsManager accessed via duckdbRouter
    });

    // 6. API Executor - uses convexClient from data-layer
    const apiExecutor = new ApiExecutor({
      convexClient,
      convexQueryClient,
      schemaRegistry,
    });

    // 7. Optimistic Updater - uses queryClient from data-layer
    const optimisticUpdater = new OptimisticUpdater({ queryClient });

    // 8. Rollback Manager
    const rollbackManager = new RollbackManager({ queryClient, optimisticUpdater });

    // 9. Query Orchestrator - coordinates everything
    const orchestrator = new QueryOrchestrator({
      schemaRegistry,
      decisionEngine,
      tableExtractor,
      fileManager,
      apiExecutor,
      sqlCompiler,
      duckdbRouter,
      convexClient,
      convexQueryClient,
      syncCoordinator,
      dataSourceApi: config.dataSourceApi,
      defaultStaleTime,
    });

    return {
      decisionEngine,
      sqlCompiler,
      schemaRegistry,
      tableExtractor,
      fileManager,
      apiExecutor,
      orchestrator,
      optimisticUpdater,
      rollbackManager,
      defaultStaleTime,
      dataSourceApi: config.dataSourceApi,
      isOnline,
    };
  }, [
    queryClient,
    convexClient,
    convexQueryClient,
    duckdbRouter,
    syncCoordinator,
    config,
    defaultStaleTime,
    isOnline,
  ]);

  useEffect(() => {
    logger.info('QueryEngine initialized', {
      tables: config.tables?.length ?? 0,
      defaultStaleTime,
      isOnline,
    });
  }, [config.tables?.length, defaultStaleTime, isOnline]);

  return <QueryEngineContext.Provider value={contextValue}>{children}</QueryEngineContext.Provider>;
};
```

### 12.3 Usage in App (Unified Table Config)

```typescript
// Table metadata is defined ONCE in DataLayerConfig
// QueryEngineProvider is minimal - just needs dataSourceApi

import { DataLayerProvider } from '@foundation/data-layer';
import { QueryEngineProvider } from '@foundation/query-engine';

import { api } from '../convex/_generated/api';

const App = () => {
  return (
    // ─── TABLES DEFINED HERE (Single Source of Truth) ───────────────────────
    <DataLayerProvider
      config={{
        convexUrl: import.meta.env.VITE_CONVEX_URL,

        // Unified table registry - used by DataLayer, SyncEngine, AND QueryEngine
        tables: [
          {
            name: 'users',
            convex: {
              list: api.users.list,
              get: api.users.get,
              create: api.users.create,
              update: api.users.update,
              delete: api.users.delete,
            },
            staleTime: 5 * 60 * 1000, // 5 minutes
            conflictStrategy: 'last-write-wins',
            analytics: {
              enabled: true, // Enable DuckDB for complex queries
              freshness: 'near-realtime',
            },
          },
          {
            name: 'orders',
            convex: {
              list: api.orders.list,
              get: api.orders.get,
              create: api.orders.create,
              update: api.orders.update,
            },
            staleTime: 1 * 60 * 1000, // 1 minute (fresher data needed)
            conflictStrategy: 'server-wins',
            analytics: {
              enabled: true,
              freshness: 'eventual',
              staleTime: 10 * 60 * 1000, // Analytics can be 10 min stale
            },
          },
          {
            name: 'products',
            convex: { list: api.products.list },
            staleTime: 60 * 60 * 1000, // 1 hour (rarely changes)
            analytics: { enabled: false }, // No DuckDB for this table
          },
        ],

        // Global defaults (tables override these)
        defaultStaleTime: 5 * 60 * 1000,
        conflictStrategy: 'last-write-wins',
        enableAnalytics: true,
        enableCrossTab: true,
      }}
    >
      {/* ─── QUERY ENGINE PROVIDER (Minimal Config) ─────────────────────────── */}
      <QueryEngineProvider
        config={{
          // Only needs dataSourceApi for Parquet file metadata
          dataSourceApi: api.datasources.list,
        }}
      >
        <MyApp />
      </QueryEngineProvider>
    </DataLayerProvider>
  );
};
```

### 12.4 What Each Library Gets From TableRegistry

```typescript
// DataLayer hooks (useDLGet, useDLCreate, etc.)
const { tableRegistry } = useDataLayerInternals();
const staleTime = tableRegistry.getStaleTime('users'); // Cache config
const createRef = tableRegistry.getConvexRef('users', 'create'); // Mutation ref

// SyncEngine (via DataLayerContainer)
const strategies = tableRegistry.getTableStrategies(); // For ConflictResolver
const mergeConfigs = tableRegistry.getTableMergeConfigs(); // For merge strategy

// QueryEngine (useQueryEngine)
const listRef = tableRegistry.getConvexRef('users', 'list'); // For API path
const canUseDuckDB = tableRegistry.isAnalyticsEnabled('users'); // For routing
const freshness = tableRegistry.getAnalyticsFreshness('users'); // For decisions
```

---

## 13. File Structure

```
libs/foundation/query-engine/
├── src/
│   ├── index.ts                          # Public exports
│   │
│   ├── types/
│   │   ├── index.ts
│   │   ├── operations.ts                 # QUERY_OPERATIONS
│   │   ├── aggregation.ts                # AGGREGATIONS
│   │   ├── dimension.ts                  # DimensionSpec
│   │   ├── measure.ts                    # MeasureSpec
│   │   ├── filter.ts                     # FilterCondition, FilterGroup
│   │   ├── join.ts                       # JoinSpec
│   │   ├── order.ts                      # OrderBySpec
│   │   ├── query.ts                      # EnterpriseQuery
│   │   ├── table.ts                      # TableConfig, ConflictStrategy
│   │   ├── datasource.ts                 # DataSourceResponse
│   │   ├── hooks.ts                      # UseQueryEngineResult
│   │   ├── config.ts                     # QueryEngineConfig
│   │   └── errors.ts                     # Error types
│   │
│   ├── registry/
│   │   ├── index.ts
│   │   └── schema-registry.ts
│   │
│   ├── engine/
│   │   ├── index.ts
│   │   ├── table-extractor.ts
│   │   ├── decision-engine.ts
│   │   ├── api-executor.ts
│   │   ├── duckdb-executor.ts
│   │   └── query-orchestrator.ts
│   │
│   ├── compiler/
│   │   ├── index.ts
│   │   └── sql-compiler.ts
│   │
│   ├── files/
│   │   ├── index.ts
│   │   └── file-manager.ts
│   │
│   ├── sync/
│   │   ├── index.ts
│   │   ├── optimistic-updater.ts
│   │   └── rollback-manager.ts
│   │
│   ├── hooks/
│   │   ├── index.ts
│   │   ├── use-query-engine.ts
│   │   ├── use-mutate-query-engine.ts
│   │   └── use-upload-file.ts
│   │
│   └── context/
│       ├── index.ts
│       ├── query-engine-context.ts
│       └── query-engine-provider.tsx
│
├── package.json
├── tsconfig.json
├── tsconfig.lib.json
├── tsconfig.spec.json
├── eslint.config.mjs
├── vite.config.mts
└── project.json
```

---

## Summary

This enterprise Query Engine provides:

| Feature | Implementation |

|---------|---------------|

| **Two Hooks** | `useQueryEngine` (declarative) + `useMutateQueryEngine` (imperative) |

| **Object-Based Format** | `DimensionSpec`, `MeasureSpec` with TypeScript safety |

| **Table Inference** | `TableExtractor` extracts from dimensions/measures/filters/joins |

| **Intelligent Routing** | `DecisionEngine` routes to API or DuckDB |

| **Real-Time Updates** | Convex `useQuery` with WebSocket subscription for API path |

| **Stale-While-Revalidate** | `lastIngestedAt` comparison for DuckDB path |

| **Optimistic Updates** | `OptimisticUpdater` applies changes immediately |

| **Rollback on Failure** | `RollbackManager` reverts failed mutations |

| **Offline Support** | `OfflineQueue` + `SyncCoordinator` from sync-engine |

| **Conflict Resolution** | Per-table strategy via `ConflictResolver` |

| **Cross-Tab Sync** | `CrossTabManager` broadcasts via BroadcastChannel |

| **User File Upload** | `useUploadFile` for CSV/Parquet/JSON |

Ready to implement?
