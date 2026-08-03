# @foundation/bridge

A high-performance, type-safe bridge layer for DuckDB routing, environment detection, and analytics data management. This library abstracts the complexity of WASM vs Native DuckDB implementations and provides unified APIs for SQL execution and view management.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
  - [High-Level Architecture](#high-level-architecture)
  - [Worker Pool Architecture](#worker-pool-architecture)
  - [Data Flow](#data-flow)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [Bridge Types](#bridge-types)
  - [Query Modes](#query-modes)
  - [Priority Levels](#priority-levels)
  - [Lifecycle Management](#lifecycle-management)
- [API Reference](#api-reference)
  - [DuckDBRouter](#duckdbrouter)
  - [Worker Pool](#worker-pool-api)
- [Type System](#type-system)
  - [Branded Types](#branded-types)
  - [Const Objects Pattern](#const-objects-pattern)
  - [Type Imports](#type-imports)
- [Error Handling](#error-handling)
  - [Error Hierarchy](#error-hierarchy)
  - [Error Classes](#error-classes)
  - [Type Guards](#type-guards)
  - [Error Handling Patterns](#error-handling-patterns)
- [SQL Safety Utilities](#sql-safety-utilities)
  - [Identifier Validation](#identifier-validation)
  - [SQL Building Functions](#sql-building-functions)
  - [Memoization](#memoization)
- [Configuration](#configuration)
  - [Router Configuration](#router-configuration)
  - [Pool Configuration](#pool-configuration)
  - [Validation](#validation)
- [Performance Considerations](#performance-considerations)
  - [Lazy Initialization](#lazy-initialization)
  - [Connection Reuse](#connection-reuse)
  - [View Rehydration](#view-rehydration)
  - [Query Caching](#query-caching)
- [Worker Pool (Advanced)](#worker-pool-advanced)
  - [Query Coordinator](#query-coordinator)
  - [Worker Instance](#worker-instance)
  - [Priority Queue](#priority-queue)
  - [Table Lock Manager](#table-lock-manager)
- [Best Practices](#best-practices)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Directory Structure](#directory-structure)
- [Dependencies](#dependencies)
- [Migration Guide](#migration-guide)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The Foundation Bridge library serves as the critical interface layer between application code and DuckDB, providing:

- **Unified DuckDB Access**: Single API for both browser-based WASM and Electron native implementations
- **Automatic Environment Detection**: Intelligently selects the optimal bridge type based on runtime environment
- **Resource Management**: Handles lifecycle, idle timeouts, and proper cleanup
- **SQL Safety**: Type-safe SQL identifier validation preventing injection attacks
- **High Concurrency Support**: Optional worker pool for parallel query execution

This library is designed for enterprise-grade applications requiring reliable, performant, and type-safe database access in browser environments.

---

## Features

| Feature                       | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| **Environment Detection**     | Auto-selects WASM or Native DuckDB based on runtime     |
| **Lazy Initialization**       | Bridge is only initialized when first needed            |
| **Idle Timeout**              | Automatic shutdown after configurable inactivity period |
| **View Tracking**             | Tracks and rehydrates views across bridge restarts      |
| **Transaction Support**       | Full transaction support with BEGIN, COMMIT, ROLLBACK   |
| **SQL Validation**            | Type-safe SQL identifier validation with memoization    |
| **Parallel View Rehydration** | Independent views restored in parallel                  |
| **Query Cancellation**        | AbortSignal support for cancelling long-running queries |
| **Priority Queuing**          | HIGH/NORMAL/LOW priority with FIFO within each level    |
| **Table Locking**             | Readers-writer locks for OPFS coordination              |
| **Parquet Support**           | Import/export Parquet files                             |
| **Singleton Pattern**         | Consistent factory-based singleton instances            |

---

## Architecture

### High-Level Architecture

```
                              Application Code
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DuckDBRouter                                    │
│  • Singleton pattern via createSingletonFactory                             │
│  • Auto-detects WASM vs Native environment                                  │
│  • Manages bridge lifecycle (lazy init, idle timeout)                       │
│  • Tracks view definitions for rehydration                                  │
│  • Uses Mutex for thread-safe initialization                                │
│  • Parallel view restoration using dependency graph                         │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
          ┌──────────────────────────┴──────────────────────────┐
          ▼                                                      ▼
┌─────────────────────────────┐                  ┌─────────────────────────────┐
│     WasmDuckDBBridge        │                  │    ElectronDuckDBBridge     │
│       (Browser)             │                  │        (Native)             │
├─────────────────────────────┤                  ├─────────────────────────────┤
│ • DuckDB-WASM runtime       │                  │ • IPC to main process       │
│ • Apache Arrow results      │                  │ • Native DuckDB binary      │
│ • Worker thread execution   │                  │ • File system access        │
│ • View definition tracking  │                  │ • Transaction support       │
│ • Prepared statements       │                  │                             │
└─────────────────────────────┘                  └─────────────────────────────┘
```

### Worker Pool Architecture

For high-concurrency scenarios, the library provides an optional worker pool:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            QueryCoordinator                                  │
│  • Central orchestrator for all queries                                     │
│  • Priority queue (HIGH > NORMAL > LOW) with O(1) ID lookups               │
│  • Table locking for OPFS coordination (readers-writer lock)               │
│  • Query timeouts with AbortSignal support                                  │
│  • Iterative overflow queue processing (prevents stack overflow)           │
│  • Capacity limiting (maxActiveQueries)                                    │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  WorkerInstance  │      │  WorkerInstance  │      │  WorkerInstance  │
│    DuckDB #1     │      │    DuckDB #2     │      │    DuckDB #3     │
├──────────────────┤      ├──────────────────┤      ├──────────────────┤
│ • Sequential     │      │ • Sequential     │      │ • Sequential     │
│   execution      │      │   execution      │      │   execution      │
│ • Internal queue │      │ • Internal queue │      │ • Internal queue │
│ • Cancellation   │      │ • Cancellation   │      │ • Cancellation   │
│   support        │      │   support        │      │   support        │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### Data Flow

```
Query Request
      │
      ▼
┌─────────────────┐
│ Check AbortSignal│──── Aborted? ────▶ QueryCancelledError
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Validate SQL    │──── Invalid? ────▶ SqlValidationError
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Ensure Bridge   │──── Init Mutex ────▶ WasmDuckDBBridge
│   Initialized   │                      or ElectronDuckDBBridge
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Reset Idle Timer│
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Execute Query   │──── Timeout? ────▶ QueryTimeoutError
│ (with params)   │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Convert Arrow   │
│ to QueryResult  │
└─────────────────┘
      │
      ▼
   Response
```

---

## Installation

```bash
npm install @open-zentra/foundation-bridge
```

### Peer Dependencies

Ensure the following peer dependencies are installed:

```bash
npm install @open-zentra/foundation-data-model
npm install @open-zentra/foundation-utils
npm install @open-zentra/foundation-database  # Optional, for OPFS metadata
```

---

## Quick Start

### Basic Query Execution

```typescript
import { getDuckDBRouter } from '@open-zentra/foundation-bridge';

// Get singleton router instance
const router = getDuckDBRouter({ debug: true });

// Define your result type
interface User {
  id: number;
  name: string;
  email: string;
  active: boolean;
}

// Execute a type-safe query
const result = await router.query<User>(
  'SELECT id, name, email, active FROM users WHERE active = true',
);

console.log(result.rows); // User[]
console.log(result.columns); // ['id', 'name', 'email', 'active']
console.log(result.types); // ['INTEGER', 'VARCHAR', 'VARCHAR', 'BOOLEAN']
console.log(result.executionTimeMs); // 12.5
```

### Parameterized Queries

```typescript
const userId = 42;
const result = await router.query<User>('SELECT * FROM users WHERE id = ?', { params: [userId] });
```

### View Management

```typescript
import { getDuckDBRouter } from '@open-zentra/foundation-bridge';
import { Timestamp } from '@open-zentra/foundation-data-model';

const router = getDuckDBRouter();

// Create a view (tracked for automatic rehydration)
await router.createView({
  name: 'active_users',
  sql: 'SELECT * FROM users WHERE active = true',
  dependencies: ['users'],
  createdAt: Timestamp.now(),
});

// Query the view
const result = await router.query('SELECT COUNT(*) as count FROM active_users');

// Views are automatically restored after idle shutdown
```

### Transactions

```typescript
const router = getDuckDBRouter();

try {
  await router.beginTransaction();

  await router.execute('INSERT INTO users (name, email) VALUES (?, ?)', {
    params: ['Alice', 'alice@example.com'],
  });
  await router.execute('INSERT INTO audit_log (action, user_id) VALUES (?, ?)', {
    params: ['USER_CREATED', 1],
  });

  await router.commit();
} catch (error) {
  await router.rollback();
  throw error;
}
```

### Query Cancellation

```typescript
import { isQueryCancelledError } from '@open-zentra/foundation-bridge';

const controller = new AbortController();

// Cancel after 5 seconds
const timeout = setTimeout(() => controller.abort(), 5000);

try {
  const result = await router.query('SELECT * FROM very_large_table', {
    signal: controller.signal,
  });
  clearTimeout(timeout);
} catch (error) {
  if (isQueryCancelledError(error)) {
    console.log('Query was cancelled by user');
  }
}
```

---

## Core Concepts

### Bridge Types

The library supports two DuckDB implementations. **Constants use CAPITAL_SNAKE_CASE**; **types use PascalCase**.

| Type   | Constant             | Environment | Use Case                                      |
| ------ | -------------------- | ----------- | --------------------------------------------- |
| WASM   | `BRIDGE_TYPE.WASM`   | Browser     | Default for web applications                  |
| Native | `BRIDGE_TYPE.NATIVE` | Electron    | Native file system access, better performance |

```typescript
import { BRIDGE_TYPE } from '@open-zentra/foundation-bridge';
import type { BridgeType } from '@open-zentra/foundation-bridge';

// Force a specific bridge type
const router = getDuckDBRouter({
  forceBridgeType: BRIDGE_TYPE.WASM,
});
```

The router auto-detects the appropriate bridge:

1. If Electron IPC (`window.electronDuckDB`) is available → Native bridge
2. Otherwise → WASM bridge

### Query Modes

When using the worker pool, queries specify their lock mode. Use **constants** (CAPITAL_SNAKE) for values and **PascalCase types** for type annotations.

| Mode  | Constant           | Behavior                                      |
| ----- | ------------------ | --------------------------------------------- |
| Read  | `QUERY_MODE.READ`  | Allows concurrent access with other readers   |
| Write | `QUERY_MODE.WRITE` | Exclusive access, blocks all other operations |

```typescript
import { QUERY_MODE } from '@open-zentra/foundation-bridge';
import type { QueryLockMode } from '@open-zentra/foundation-bridge';

// Read queries can run concurrently
await pool.query({
  sql: 'SELECT * FROM users',
  tables: ['users'],
  mode: QUERY_MODE.READ,
});

// Write queries get exclusive access
await pool.query({
  sql: 'INSERT INTO users VALUES (...)',
  tables: ['users'],
  mode: QUERY_MODE.WRITE,
});
```

### Priority Levels

Queries are processed in priority order. Use **PRIORITY** (constant) for values and **PriorityLevel** (type) for annotations.

| Priority | Constant          | Numeric Value | Use Case                          |
| -------- | ----------------- | ------------- | --------------------------------- |
| High     | `PRIORITY.HIGH`   | 3             | User-facing, interactive queries  |
| Normal   | `PRIORITY.NORMAL` | 2             | Background data loading (default) |
| Low      | `PRIORITY.LOW`    | 1             | Maintenance, cleanup, analytics   |

```typescript
import { PRIORITY, QUERY_MODE } from '@open-zentra/foundation-bridge';
import type { PriorityLevel } from '@open-zentra/foundation-bridge';

// High-priority user request
await pool.query({
  sql: 'SELECT * FROM dashboard_data',
  tables: ['dashboard_data'],
  mode: QUERY_MODE.READ,
  priority: PRIORITY.HIGH,
});
```

### Lifecycle Management

The router manages bridge lifecycle automatically:

1. **Lazy Initialization**: Bridge is created on first query
2. **Idle Timeout**: Bridge shuts down after inactivity (default: 30s)
3. **View Rehydration**: Views are automatically restored after restart
4. **Resource Cleanup**: Proper disposal of connections, workers, and timers

```typescript
import { Milliseconds } from '@open-zentra/foundation-data-model';

const router = getDuckDBRouter({
  idleTimeout: Milliseconds.from(60_000), // 60 seconds
  autoInit: true, // Auto-init on first query
  debug: true, // Enable logging
});

// Get current status
const status = router.getStatus();
console.log(status.initialized); // true/false
console.log(status.busy); // true if initializing
console.log(status.lastActivityAt); // Timestamp
console.log(status.type); // 'wasm' or 'native'
```

---

## API Reference

### DuckDBRouter

Main entry point for DuckDB operations.

#### Factory Functions

```typescript
// Get or create singleton router
const router = getDuckDBRouter(config?: DuckDBRouterConfig): DuckDBRouter;

// Reset router (for testing or config change)
await resetDuckDBRouter(): Promise<void>;

// Check if router exists
const exists = hasDuckDBRouter(): boolean;
```

#### DuckDBRouterConfig

```typescript
interface DuckDBRouterConfig {
  /** Force a specific bridge type (auto-detects if not set) */
  forceBridgeType?: BridgeType;

  /** Idle timeout before shutdown in ms (default: 30000) */
  idleTimeout?: Milliseconds;

  /** Enable debug logging */
  debug?: boolean;

  /** Auto-initialize on first query (default: true) */
  autoInit?: boolean;
}
```

#### Methods

```typescript
interface DuckDBRouter {
  // Lifecycle
  initialize(): Promise<void>;
  shutdown(): Promise<void>;
  isInitialized(): boolean;

  // Query Execution
  query<T = Record<string, unknown>>(sql: string, options?: QueryOptions): Promise<QueryResult<T>>;

  execute(sql: string, options?: QueryOptions): Promise<void>;

  // File Management
  registerFile(path: string, alias: string): Promise<void>;
  unregisterFile(alias: string): Promise<void>;

  // View Management
  createView(view: ViewDefinition): Promise<void>;
  dropView(name: string): Promise<void>;
  getViews(): Promise<readonly ViewDefinition[]>;
  getViewDefinitions(): ViewDefinition[];

  // Table Management
  getTables(): Promise<readonly TableInfo[]>;
  exists(name: string): Promise<boolean>;

  // Parquet Operations
  exportToParquet(tableName: string, path: string): Promise<void>;
  importParquet(path: string, tableName: string): Promise<void>;

  // Transactions
  beginTransaction(): Promise<void>;
  commit(): Promise<void>;
  rollback(): Promise<void>;

  // Status
  getStatus(): DuckDBBridgeStatus;
  getBridgeType(): BridgeType | null;

  // Rehydration
  rehydrate(): Promise<void>;
}
```

#### QueryOptions

```typescript
interface QueryOptions {
  /** Parameterized query values */
  params?: readonly unknown[];

  /** Query timeout in milliseconds */
  timeout?: Milliseconds;

  /** Maximum rows to return */
  limit?: number;

  /** Offset for pagination */
  offset?: number;

  /** AbortSignal for cancellation */
  signal?: AbortSignal;
}
```

#### QueryResult

```typescript
interface QueryResult<T = Record<string, unknown>> {
  /** Result rows */
  rows: T[];

  /** Column names */
  columns: string[];

  /** Column types (DuckDB type strings) */
  types: string[];

  /** Rows affected (for mutations) */
  rowsAffected?: number;

  /** Execution time in milliseconds */
  executionTimeMs: number;
}
```

### Worker Pool API

For high-concurrency scenarios:

```typescript
// Create a new pool (non-singleton)
const pool = await createDuckDBPool(config?: DuckDBPoolConfig);

// Get singleton pool
const pool = await getDuckDBPool(config?: DuckDBPoolConfig);

// Reset singleton pool
await resetDuckDBPool();

// Check if pool exists
hasDuckDBPool(): boolean;
```

#### DuckDBPool Interface

```typescript
interface DuckDBPool {
  query<T = Record<string, unknown>>(request: QueryRequest<T>): Promise<PoolQueryResult<T>>;

  getStatus(): PoolStatus;
  getConfig(): ResolvedPoolConfig;
  isReady(): boolean;
  shutdown(): Promise<void>;
}
```

---

## Type System

### Branded Types

Import branded types from `@open-zentra/foundation-data-model`:

```typescript
import {
  QueryId,
  WorkerId,
  SqlIdentifier,
  SqlTableName,
  Milliseconds,
  Timestamp,
} from '@open-zentra/foundation-data-model';

// Create IDs
const queryId = QueryId.create();       // "q_1234567890_abc"
const workerId = WorkerId.create(1);    // "worker_1"

// Create timestamps
const now = Timestamp.now();
const past = Timestamp.from(1640000000000);

// Create durations
const timeout = Milliseconds.from(5000);
const fromSeconds = Milliseconds.fromSeconds(30);

// Type safety prevents mixing
function executeQuery(qid: QueryId, wid: WorkerId) { ... }
executeQuery(workerId, queryId); // ❌ Type error!
```

### Naming Conventions and Const Objects

**Constants** (including enum-like const objects) use **CAPITAL_SNAKE_CASE**. **Types** (interfaces, type aliases) use **PascalCase**. Type and const must not share the same name.

```typescript
// Constants (CAPITAL_SNAKE_CASE)
export const PRIORITY = {
  HIGH: 'high',
  NORMAL: 'normal',
  LOW: 'low',
} as const;

// Type (PascalCase), derived from const
export type PriorityLevel = (typeof PRIORITY)[keyof typeof PRIORITY];

// Usage
const p1: PriorityLevel = PRIORITY.HIGH; // Value from const, type from type
const p2: PriorityLevel = 'high'; // Literal still valid
const p3: PriorityLevel = 'invalid'; // ❌ Type error
```

Available constants (CAPITAL_SNAKE) and their types (PascalCase):

- `BRIDGE_TYPE` / `BridgeType` - `'wasm' | 'native'`
- `PRIORITY` / `PriorityLevel` - `'high' | 'normal' | 'low'`
- `QUERY_MODE` / `QueryLockMode` - `'read' | 'write'`
- `WORKER_STATUS` / `WorkerStatus` - `'initializing' | 'idle' | 'busy' | 'error' | 'shutdown'`
- `CANCELLATION_REASON` / `CancellationReasonKind` - `'user' | 'shutdown' | 'timeout'`
- `RUNTIME_ENVIRONMENT` / `RuntimeEnvironmentKind` - `'electron' | 'web' | 'node'`
- `STORAGE_STRATEGY` / `StorageStrategyKind` - `'opfs' | 'indexeddb' | 'memory'`

### Type Imports

Follow these import conventions:

```typescript
// Branded types - from foundation-data-model

// Interface types - from bridge types
import type {
  DuckDBBridge,
  DuckDBBridgeStatus,
  PoolStatus,
  QueryOptions,
  QueryResult,
  ViewDefinition,
  WorkerInfo,
  WorkerStatus,
} from '@open-zentra/foundation-bridge';
// WORKER_STATUS const, WorkerStatus type - from types/pool or internal
import { WORKER_STATUS } from '@open-zentra/foundation-bridge';
// Const objects (values) - from bridge constants
import { BridgeType, Priority, QueryMode } from '@open-zentra/foundation-bridge/constants';
import {
  Milliseconds,
  QueryId,
  SqlIdentifier,
  SqlTableName,
  Timestamp,
  WorkerId,
} from '@open-zentra/foundation-data-model';

// Or from internal.ts for foundation libraries:
import { BridgeType, Priority, QueryMode } from './constants';
```

---

## Error Handling

### Relationship with Foundation Utils Error Module

Foundation **Utils** provides **generic** error utilities; Foundation **Bridge** provides **domain-specific** error classes and guards. Both are used together.

| Concern                                             | Use                                                                                                             | Source                                     |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| Normalize `unknown` to `Error`, get message/name    | `normalizeError`, `getErrorMessage`, `getErrorName`, `formatErrorMessage`                                       | `@open-zentra/foundation-utils`      |
| Generic guards (abort, network, timeout by message) | `isAbortError`, `isTimeoutError`, `isNetworkError`, `hasErrorCode` (generic)                                    | `@open-zentra/foundation-utils`      |
| Error handling strategy (retry/report/log)          | `categorizeError`, `getErrorStrategy`, `createErrorHandler`, `handleErrorByCategory`                            | `@open-zentra/foundation-utils`      |
| Domain error classes (Bridge)                       | `QueryTimeoutError`, `BridgeNotInitializedError`, etc.                                                          | This library                               |
| Domain type guards (Bridge)                         | `isQueryTimeoutError`, `isQueryCancelledError`, etc.                                                            | This library                               |
| Foundation error base and codes                     | `FoundationError`, `FOUNDATION_ERROR_CODE`, `isFoundationError`, `hasErrorCode(error, FOUNDATION_ERROR_CODE.*)` | `@open-zentra/foundation-data-model` |

**Why Bridge has its own error “things”:**

- **Utils does not define domain error classes.** It only provides generic helpers (normalize, message extraction, generic guards like `isAbortError`). Bridge needs **typed, domain-specific errors** (e.g. `QueryTimeoutError` with `queryId`, `timeoutMs`) that extend `FoundationError` and use `FOUNDATION_ERROR_CODE`.
- **Utils cannot implement “is this a Bridge error?”** because it doesn’t depend on Bridge. So Bridge provides **domain type guards** (`isQueryTimeoutError`, etc.) that do `instanceof` checks against its own classes.

**What Bridge already reuses from Utils:**

- `normalizeError` and `getErrorMessage` are used in bridge code (e.g. `wasm-bridge`, `router`, worker pool) when catching `unknown` and logging or wrapping.

**What you can reuse from Utils in your code:**

- Use `isAbortError(error)` from Utils when you want to treat `AbortController` aborts like cancellations, in addition to `isQueryCancelledError(error)`.
- Use `categorizeError(error)` and `getErrorStrategy(category)` from Utils to decide retry / report / log in catch blocks.
- Use `createErrorHandler({ context: 'MyModule', onError })` from Utils for consistent logging and reporting.
- Use `formatErrorMessage(context, message)` from Utils for consistent log prefixes.

### Error Hierarchy

All bridge errors extend `FoundationError`:

```
Error
  └── FoundationError (from foundation-data-model)
        └── BridgeError (base for all bridge errors)
              ├── QueryTimeoutError
              ├── QueryCancelledError
              ├── QueryExecutionError
              ├── SqlValidationError
              ├── PoolShutdownError
              ├── WorkerError
              ├── WorkerInitializationError
              ├── NoAvailableWorkersError
              ├── PoolCapacityError
              ├── BridgeNotInitializedError
              ├── BridgeInitializationError
              ├── OpfsNotFoundError
              ├── OpfsPermissionError
              ├── OpfsWriteError
              └── ConfigurationError
```

### Error Classes

#### Query Errors

```typescript
import {
  QueryCancelledError,
  QueryExecutionError,
  QueryTimeoutError,
  SqlValidationError,
} from '@open-zentra/foundation-bridge';

// QueryTimeoutError - query exceeded timeout
const error = new QueryTimeoutError(queryId, timeoutMs, sql);
error.queryId; // QueryId
error.timeoutMs; // Milliseconds
error.sql; // string | undefined (first 100 chars)

// QueryCancelledError - query was cancelled
const error = new QueryCancelledError(queryId, reason);
error.queryId; // QueryId
error.reason; // CancellationReason ('user' | 'shutdown' | 'timeout')

// QueryExecutionError - query execution failed
const error = new QueryExecutionError(queryId, sql, cause);
error.queryId; // QueryId
error.sql; // string (first 200 chars)
error.cause; // Error

// SqlValidationError - invalid SQL identifier
const error = new SqlValidationError(identifier, reason);
error.identifier; // string
error.reason; // string
```

#### Pool Errors

```typescript
import {
  NoAvailableWorkersError,
  PoolCapacityError,
  PoolShutdownError,
  WorkerError,
  WorkerInitializationError,
} from '@open-zentra/foundation-bridge';

// PoolShutdownError - pool is shutting down
const error = new PoolShutdownError(pendingQueries);

// WorkerError - general worker error
const error = new WorkerError(workerId, message, cause);

// WorkerInitializationError - worker failed to start
const error = new WorkerInitializationError(workerId, cause);

// NoAvailableWorkersError - all workers busy
const error = new NoAvailableWorkersError(totalWorkers, busyWorkers);

// PoolCapacityError - pool at max capacity
const error = new PoolCapacityError(maxCapacity, currentSize);
```

#### Bridge Errors

```typescript
import {
  BridgeInitializationError,
  BridgeNotInitializedError,
  ConfigurationError,
  OpfsNotFoundError,
  OpfsPermissionError,
  OpfsWriteError,
} from '@open-zentra/foundation-bridge';
// OpfsNotSupportedError should be imported from foundation-database
// (OPFS is fundamentally a database concern)
import { OpfsNotSupportedError } from '@open-zentra/foundation-database';
```

### Type Guards

```typescript
import {
  isBridgeError,
  isBridgeInitializationError,
  isBridgeNotInitializedError,
  isConfigurationError,
  isNoAvailableWorkersError,
  isOpfsNotFoundError,
  isOpfsPermissionError,
  isOpfsWriteError,
  isPoolCapacityError,
  isPoolShutdownError,
  isQueryCancelledError,
  isQueryExecutionError,
  isQueryTimeoutError,
  isSqlValidationError,
  isWorkerError,
  isWorkerInitializationError,
} from '@open-zentra/foundation-bridge';

// OpfsNotSupportedError and isOpfsNotSupportedError: import from '@open-zentra/foundation-database'

if (isQueryTimeoutError(error)) {
  console.error(`Query ${error.queryId} timed out after ${error.timeoutMs}ms`);
}
```

### Error Handling Patterns

```typescript
import {
  isBridgeError,
  isQueryCancelledError,
  isQueryTimeoutError,
  isSqlValidationError,
} from '@open-zentra/foundation-bridge';
import {
  FOUNDATION_ERROR_CODE,
  hasErrorCode,
  isFoundationError,
} from '@open-zentra/foundation-data-model';

try {
  const result = await router.query(sql);
} catch (error) {
  // Handle specific errors
  if (isQueryTimeoutError(error)) {
    // Retry with longer timeout
    return await router.query(sql, { timeout: Milliseconds.from(60_000) });
  }

  if (isQueryCancelledError(error)) {
    // User cancelled - no action needed
    return null;
  }

  if (isSqlValidationError(error)) {
    // Show validation error to user
    throw new UserInputError(`Invalid identifier: ${error.identifier}`);
  }

  // Check error codes
  if (hasErrorCode(error, FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT)) {
    // Handle by error code
  }

  // Log structured error
  if (isBridgeError(error)) {
    logger.error('Bridge error', error.toJSON());
  }

  // Re-throw unknown errors
  throw error;
}
```

---

## SQL Safety Utilities

### Identifier Validation

```typescript
import {
  isValidIdentifier,
  validateIdentifier,
  validateTableName,
} from '@open-zentra/foundation-bridge';

// Validate and create branded type (throws on invalid)
const safeName = validateIdentifier('users'); // SqlIdentifier
const safeTable = validateTableName('events'); // SqlTableName

// These throw SqlValidationError:
validateIdentifier(''); // Empty
validateIdentifier('1table'); // Starts with number
validateIdentifier('DROP'); // Reserved word
validateIdentifier('user-name'); // Invalid character
validateIdentifier('a'.repeat(300)); // Too long (max 256)

// Check without throwing
if (isValidIdentifier(userInput)) {
  const safeName = validateIdentifier(userInput);
}
```

### SQL Building Functions

```typescript
import {
  applyLimitOffset,
  buildCreateViewSql,
  buildDropViewSql,
  buildParameterizedSql,
  escapeString,
  quoteIdentifier,
} from '@open-zentra/foundation-bridge';

// Quote identifier (handles double-quotes)
quoteIdentifier(validateIdentifier('users'));
// → '"users"'

quoteIdentifier(validateIdentifier('user_name'));
// → '"user_name"'

// Build CREATE VIEW
const viewSql = buildCreateViewSql(
  validateIdentifier('active_users'),
  'SELECT * FROM users WHERE active = true',
  true, // orReplace
);
// → 'CREATE OR REPLACE VIEW "active_users" AS SELECT * FROM users WHERE active = true'

// Build DROP VIEW
const dropSql = buildDropViewSql(validateIdentifier('old_view'), true);
// → 'DROP VIEW IF EXISTS "old_view"'

// Escape string values (prefer parameterized queries)
const escaped = escapeString("O'Brien");
// → "O''Brien"

// Apply pagination
const paginatedSql = applyLimitOffset('SELECT * FROM users', 10, 20);
// → 'SELECT * FROM users LIMIT 10 OFFSET 20'

// Validate parameterized SQL
const { sql, placeholderCount } = buildParameterizedSql(
  'SELECT * FROM users WHERE id = ? AND name = ?',
  2, // expected param count
);
// Throws if placeholder count doesn't match
```

### Memoization

The `validateIdentifier` function uses LRU memoization for performance:

```typescript
// Implementation details:
// - Validated identifiers cached (up to 1000 entries)
// - Invalid identifiers also cached (prevents repeated validation)
// - LRU eviction when cache is full

// First call validates
const name1 = validateIdentifier('users'); // Validates

// Subsequent calls use cache
const name2 = validateIdentifier('users'); // Cache hit!
```

---

## Configuration

### Router Configuration

| Option            | Type           | Default     | Description                                   |
| ----------------- | -------------- | ----------- | --------------------------------------------- |
| `forceBridgeType` | `BridgeType`   | `undefined` | Force WASM or Native (auto-detect if not set) |
| `idleTimeout`     | `Milliseconds` | `30000`     | Shutdown after inactivity (0 to disable)      |
| `debug`           | `boolean`      | `false`     | Enable debug logging                          |
| `autoInit`        | `boolean`      | `true`      | Initialize on first query                     |

```typescript
import { BridgeType, getDuckDBRouter } from '@open-zentra/foundation-bridge';
import { Milliseconds } from '@open-zentra/foundation-data-model';

const router = getDuckDBRouter({
  forceBridgeType: BRIDGE_TYPE.WASM,
  idleTimeout: Milliseconds.from(60_000),
  debug: process.env.NODE_ENV === 'development',
  autoInit: true,
});
```

### Pool Configuration

| Option                 | Type                   | Default                       | Description                  |
| ---------------------- | ---------------------- | ----------------------------- | ---------------------------- |
| `workerCount`          | `number`               | `min(hardwareConcurrency, 8)` | Number of workers            |
| `maxQueuePerWorker`    | `number`               | `10`                          | Max queries per worker queue |
| `maxActiveQueries`     | `number`               | `1000`                        | Max total active queries     |
| `defaultQueryTimeout`  | `Milliseconds`         | `30000`                       | Default timeout              |
| `workerInitTimeout`    | `Milliseconds`         | `10000`                       | Worker startup timeout       |
| `workerIdleTimeout`    | `Milliseconds \| null` | `null`                        | Worker idle shutdown         |
| `enableTableLocking`   | `boolean`              | `true`                        | Enable OPFS coordination     |
| `restartFailedWorkers` | `boolean`              | `true`                        | Auto-restart failed workers  |
| `debug`                | `boolean`              | `false`                       | Enable debug logging         |

```typescript
import { getDuckDBPool } from '@open-zentra/foundation-bridge';
import { Milliseconds } from '@open-zentra/foundation-data-model';

const pool = await getDuckDBPool({
  workerCount: 4,
  maxQueuePerWorker: 20,
  maxActiveQueries: 500,
  defaultQueryTimeout: Milliseconds.from(30_000),
  workerInitTimeout: Milliseconds.from(15_000),
  enableTableLocking: true,
  restartFailedWorkers: true,
  debug: true,
});
```

### Validation

```typescript
import {
  resolvePoolConfig,
  validatePoolConfig,
  validateRouterConfig,
} from '@open-zentra/foundation-bridge';

// Validate configuration
const poolResult = validatePoolConfig(config);
if (!poolResult.valid) {
  console.error('Invalid pool config:', poolResult.errors);
}

const routerResult = validateRouterConfig(config);
if (!routerResult.valid) {
  console.error('Invalid router config:', routerResult.errors);
}

// Get resolved config with defaults
const resolved = resolvePoolConfig({
  workerCount: 4,
});
// resolved.workerCount = 4
// resolved.maxQueuePerWorker = 10 (default)
// resolved.defaultQueryTimeout = Milliseconds.from(30000) (default)
// ... etc
```

---

## Performance Considerations

### Lazy Initialization

The bridge is only initialized when first needed:

```typescript
const router = getDuckDBRouter(); // No initialization yet

// First query triggers initialization
const result = await router.query('SELECT 1'); // Initializes here
```

### Connection Reuse

A single connection is maintained per bridge instance:

- Avoids connection overhead per query
- Supports transactions across multiple statements
- Automatically recreated after idle shutdown

### View Rehydration

Views are restored in parallel with dependency ordering:

```typescript
// Views are automatically tracked
await router.createView({
  name: 'user_stats',
  sql: 'SELECT user_id, COUNT(*) FROM events GROUP BY user_id',
  dependencies: ['events'],
  createdAt: Timestamp.now(),
});

// After idle shutdown and rehydration:
// - Files are re-registered first
// - Views are restored in dependency order
// - Independent views are created in parallel
```

### Query Caching

For frequently executed queries, consider using prepared statements:

```typescript
// Parameterized queries use prepared statements internally
const result = await router.query('SELECT * FROM users WHERE id = ?', { params: [userId] });
// DuckDB prepares the statement once and reuses it
```

---

## Worker Pool (Advanced)

### Query Coordinator

The central orchestrator for the pool:

```typescript
import { QueryCoordinator } from '@open-zentra/foundation-bridge';

const coordinator = new QueryCoordinator({
  workerCount: 4,
  maxActiveQueries: 1000,
  enableTableLocking: true,
});

await coordinator.initialize();

const result = await coordinator.query({
  sql: 'SELECT * FROM users',
  tables: ['users'],
  mode: QUERY_MODE.READ,
  priority: PRIORITY.NORMAL,
});

await coordinator.shutdown();
```

Lock acquisition is performed at dispatch time (right before worker execution), not while waiting in overflow queues. This prevents queued requests from holding locks while capacity is unavailable and keeps read/write coordination correct under high contention.

### Worker Instance

Individual worker wrapper:

```typescript
import { WorkerInstance } from '@open-zentra/foundation-bridge';

const worker = new WorkerInstance(WorkerId.create(1), { debug: true });
await worker.initialize();

// Workers execute queries sequentially
const result = await worker.execute(QueryId.create(), 'SELECT 1', abortSignal);

await worker.shutdown();
```

### Priority Queue

O(1) priority queue implementation:

```typescript
import { PriorityQueue } from '@open-zentra/foundation-bridge';

const queue = new PriorityQueue<QueryItem>();

// Enqueue with priority
queue.enqueue(query1, PRIORITY.HIGH);
queue.enqueue(query2, PRIORITY.NORMAL);
queue.enqueue(query3, PRIORITY.LOW);

// Dequeue in priority order
const next = queue.dequeue(); // query1 (HIGH)

// O(1) operations
queue.size(); // Total size
queue.sizeAt(PRIORITY.HIGH); // Size at priority
queue.isEmpty();
queue.peek();
queue.remove(predicate);
queue.removeById(id);
queue.clear();
```

### Table Lock Manager

Readers-writer lock implementation:

```typescript
import { TableLockManager } from '@open-zentra/foundation-bridge';

const lockManager = new TableLockManager({ debug: true });

// Multiple readers allowed
await lockManager.acquireLocks(['users'], QUERY_MODE.READ);
await lockManager.acquireLocks(['users'], QUERY_MODE.READ);

// Writers get exclusive access
await lockManager.acquireLocks(['orders'], QUERY_MODE.WRITE);

// Release locks
lockManager.releaseLocks(['users'], QUERY_MODE.READ);
lockManager.releaseLocks(['orders'], QUERY_MODE.WRITE);

// Status
lockManager.isLocked('users');
lockManager.isWriteLocked('orders');
lockManager.getReaderCount('users');
lockManager.getLockedTables();
lockManager.getLockStatus();
```

---

## Best Practices

### 1. Prefer Instance-Scoped Routers and Pools

```typescript
// ✅ Good - explicit lifecycle ownership
const router = createDuckDBRouter({ debug: true });
await router.initialize();
try {
  const result = await router.query('SELECT 1');
  console.log(result.rows);
} finally {
  await router.shutdown();
}

// ✅ Also valid when you intentionally want app-wide shared state
const sharedRouter = getDuckDBRouter();

// ❌ Avoid unmanaged global resets in app runtime paths
await resetDuckDBRouter();
```

### 2. Always Validate SQL Identifiers

```typescript
// ✅ Good - validates input
const safeName = validateIdentifier(userInput);
await router.query(`SELECT * FROM ${quoteIdentifier(safeName)}`);

// ❌ Bad - SQL injection risk
await router.query(`SELECT * FROM ${userInput}`);
```

### 3. Use Parameterized Queries

```typescript
// ✅ Good - parameterized
await router.query('SELECT * FROM users WHERE id = ?', { params: [userId] });

// ❌ Bad - string interpolation
await router.query(`SELECT * FROM users WHERE id = ${userId}`);
```

### 4. Handle Errors Specifically

```typescript
// ✅ Good - specific error handling
if (isQueryTimeoutError(error)) {
  // Handle timeout
} else if (isQueryCancelledError(error)) {
  // Handle cancellation
}

// ❌ Bad - generic catch
catch (error) {
  console.log('Something went wrong');
}
```

### 5. Use AbortSignal for Long Queries

```typescript
// ✅ Good - cancellable query
const controller = new AbortController();
await router.query(sql, { signal: controller.signal });

// In cleanup or timeout
controller.abort();
```

### 6. Import from Correct Packages

```typescript
// ✅ Good - direct imports

// ❌ Bad - importing from wrong package
import { Milliseconds } from '@open-zentra/foundation-bridge';
import { Milliseconds, Timestamp } from '@open-zentra/foundation-data-model';
import { sleep, withTimeout } from '@open-zentra/foundation-utils';
```

### 7. Clean Up Resources

```typescript
// ✅ Good - proper cleanup
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 5000);

try {
  const result = await router.query(sql, { signal: controller.signal });
  clearTimeout(timeout);
  return result;
} catch (error) {
  clearTimeout(timeout);
  throw error;
}
```

---

## Testing

### Running Tests

```bash
# Run all bridge tests
nx test foundation-bridge

# Run specific test file
nx test foundation-bridge --testFile=sql.spec.ts

# Watch mode
nx test foundation-bridge --watch

# With coverage
nx test foundation-bridge --coverage
```

### Test Setup

```typescript
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { getDuckDBRouter, resetDuckDBRouter } from '@open-zentra/foundation-bridge';

describe('DuckDBRouter', () => {
  beforeEach(async () => {
    // Reset to clean state
    await resetDuckDBRouter();
  });

  afterEach(async () => {
    // Clean up
    await resetDuckDBRouter();
  });

  it('should execute query', async () => {
    const router = getDuckDBRouter({ debug: true });
    const result = await router.query('SELECT 1 as value');
    expect(result.rows).toEqual([{ value: 1 }]);
  });
});
```

---

## Troubleshooting

### Common Issues

#### Bridge Not Initializing

```typescript
// Check if WASM assets are loaded
console.log('DuckDB WASM available:', typeof window !== 'undefined');

// Enable debug logging
const router = getDuckDBRouter({ debug: true });
```

#### Query Timeout

```typescript
// Increase timeout for large queries
await router.query(sql, {
  timeout: Milliseconds.from(120_000), // 2 minutes
});
```

#### OPFS Not Supported

```typescript
import { isOpfsSupported } from '@open-zentra/foundation-utils';

if (!isOpfsSupported()) {
  console.warn('OPFS not supported in this browser');
  // Fall back to in-memory storage
}
```

#### Views Not Rehydrating

```typescript
// Check view definitions are being tracked
const views = router.getViewDefinitions();
console.log('Tracked views:', views);

// Force rehydration
await router.rehydrate();
```

---

## Directory Structure

```
libs/foundation/bridge/
├── src/
│   ├── constants/
│   │   └── index.ts           # DEFAULTS, Priority, QueryMode, BridgeType, RuntimeEnvironment, StorageStrategy, SQL
│   ├── detection/
│   │   ├── detector.ts        # EnvironmentDetector
│   │   └── index.ts
│   ├── duckdb/
│   │   ├── arrow-converter.ts # Apache Arrow → JavaScript
│   │   ├── router.ts          # DuckDBRouter (main entry)
│   │   ├── types.ts           # DuckDBRow, DuckDBResult
│   │   └── index.ts
│   ├── errors/
│   │   ├── base-error.ts      # BridgeError base class
│   │   ├── bridge-errors.ts   # Init, OPFS, Config errors
│   │   ├── pool-errors.ts     # Worker, capacity errors
│   │   ├── query-errors.ts    # Timeout, cancelled, execution
│   │   ├── type-guards.ts     # Error type checking
│   │   └── index.ts
│   ├── lifecycle/
│   │   ├── idle-timer.ts      # IdleTimer class
│   │   ├── rehydration.ts     # RehydrationController
│   │   └── index.ts
│   ├── native/
│   │   ├── electron-bridge.ts # ElectronDuckDBBridge
│   │   └── index.ts
│   ├── types/
│   │   ├── bridge.ts          # DuckDBBridge interface
│   │   ├── pool.ts            # Pool types
│   │   └── index.ts
│   ├── utils/
│   │   ├── sql.ts             # SQL validation/building
│   │   ├── sql.spec.ts
│   │   ├── validation.ts      # Config validation
│   │   ├── validation.spec.ts
│   │   └── index.ts
│   ├── wasm/
│   │   ├── duckdb-init.ts     # DuckDB-WASM setup
│   │   ├── wasm-bridge.ts     # WasmDuckDBBridge
│   │   ├── pool/
│   │   │   ├── factory.ts
│   │   │   ├── priority-queue.ts
│   │   │   ├── query-coordinator.ts
│   │   │   ├── table-lock-manager.ts
│   │   │   ├── worker-instance.ts
│   │   │   ├── worker-pool.ts
│   │   │   └── index.ts
│   │   └── index.ts
│   ├── index.ts               # Public API exports
│   └── internal.ts            # Internal exports
├── README.md
├── package.json
├── tsconfig.json
├── tsconfig.lib.json
└── vite.config.mts
```

---

## Dependencies

### Runtime Dependencies

| Package                                    | Purpose                      |
| ------------------------------------------ | ---------------------------- |
| `@duckdb/duckdb-wasm`                      | DuckDB WASM runtime          |
| `@open-zentra/foundation-data-model` | Branded types, error classes |
| `@open-zentra/foundation-utils`      | Utility functions            |
| `apache-arrow`                             | Arrow format support         |
| `react-fast-compare`                       | Deep equality comparison     |

### Peer Dependencies

| Package                                  | Purpose                           |
| ---------------------------------------- | --------------------------------- |
| `@open-zentra/foundation-database` | IndexedDB for metadata (optional) |

### Dev Dependencies

| Package      | Purpose             |
| ------------ | ------------------- |
| `vitest`     | Testing framework   |
| `vite`       | Build tool          |
| `typescript` | TypeScript compiler |

---

## Migration Guide

### From v2.x to v3.x

#### Naming Conventions: Constants (CAPITAL_SNAKE_CASE) and Types (PascalCase)

Constants and types no longer share the same name. **Const objects** use **CAPITAL_SNAKE_CASE**; **types** use **PascalCase**:

| Before (v2)          | After (v3) – constant | After (v3) – type        |
| -------------------- | --------------------- | ------------------------ |
| `Priority`           | `PRIORITY`            | `PriorityLevel`          |
| `QueryMode`          | `QUERY_MODE`          | `QueryLockMode`          |
| `BridgeType`         | `BRIDGE_TYPE`         | `BridgeType`             |
| `WorkerStatus`       | `WORKER_STATUS`       | `WorkerStatus`           |
| `CancellationReason` | `CANCELLATION_REASON` | `CancellationReasonKind` |
| `RuntimeEnvironment` | `RUNTIME_ENVIRONMENT` | `RuntimeEnvironmentKind` |
| `StorageStrategy`    | `STORAGE_STRATEGY`    | `StorageStrategyKind`    |

```typescript
// Before
// value

// After
import {
  BRIDGE_TYPE,
  BridgeType,
  Priority,
  PRIORITY,
  QUERY_MODE,
  QueryMode,
} from '@open-zentra/foundation-bridge';
import type {
  BridgeType,
  PriorityLevel,
  QueryLockMode,
} from '@open-zentra/foundation-bridge';

mode: QueryMode; // type
priority: Priority.HIGH;

mode: QueryLockMode; // type
priority: PRIORITY.HIGH; // value
```

#### Removed Type Guard Re-export: isOpfsNotSupportedError

`isOpfsNotSupportedError` is no longer exported from this library. Import it (and `OpfsNotSupportedError`) from the canonical source:

```typescript
// Before
import {
  isOpfsNotSupportedError,
  OpfsNotSupportedError,
} from '@open-zentra/foundation-bridge';
// After
import {
  isOpfsNotSupportedError,
  OpfsNotSupportedError,
} from '@open-zentra/foundation-database';
```

#### Removed Re-exports (OpfsNotSupportedError class)

`OpfsNotSupportedError` is no longer re-exported from this library. Import directly from the canonical source:

```typescript
// Before
import { OpfsNotSupportedError } from '@open-zentra/foundation-bridge';
// After
import { OpfsNotSupportedError } from '@open-zentra/foundation-database';
```

#### Removed Factory Functions

Factory functions for error classes have been removed. Use direct instantiation:

```typescript
// Before
// After
import { createQueryTimeoutError, QueryTimeoutError } from '@open-zentra/foundation-bridge';

const error = createQueryTimeoutError(queryId, timeoutMs, sql);

const error = new QueryTimeoutError(queryId, timeoutMs, sql);
```

Removed factory functions:

- `createQueryTimeoutError` - use `new QueryTimeoutError()`
- `createQueryCancelledError` - use `new QueryCancelledError()`
- `createQueryExecutionError` - use `new QueryExecutionError()`
- `createSqlValidationError` - use `new SqlValidationError()`
- `createPoolShutdownError` - use `new PoolShutdownError()`
- `createWorkerError` - use `new WorkerError()`
- `createWorkerInitializationError` - use `new WorkerInitializationError()`
- `createNoAvailableWorkersError` - use `new NoAvailableWorkersError()`
- `createPoolCapacityError` - use `new PoolCapacityError()`
- `createBridgeNotInitializedError` - use `new BridgeNotInitializedError()`
- `createBridgeInitializationError` - use `new BridgeInitializationError()`
- `createOpfsNotFoundError` - use `new OpfsNotFoundError()`
- `createOpfsPermissionError` - use `new OpfsPermissionError()`
- `createOpfsWriteError` - use `new OpfsWriteError()`
- `createConfigurationError` - use `new ConfigurationError()`

#### Const Objects (CAPITAL_SNAKE_CASE)

Runtime and storage constants use CAPITAL_SNAKE_CASE; use the matching PascalCase types when needed:

```typescript
import { RUNTIME_ENVIRONMENT, STORAGE_STRATEGY } from '@open-zentra/foundation-bridge';
import type {
  RuntimeEnvironmentKind,
  StorageStrategyKind,
} from '@open-zentra/foundation-bridge';

if (environment === RUNTIME_ENVIRONMENT.ELECTRON) {
  // Electron-specific logic
}

const strategy: StorageStrategyKind = STORAGE_STRATEGY.OPFS;
```

### From v1.x to v2.x

#### Import Changes

```typescript
// Before

// After (v3: use CAPITAL_SNAKE constants and PascalCase types)
import { PRIORITY, QUERY_MODE } from '@open-zentra/foundation-bridge';
import type { PriorityLevel, QueryLockMode } from '@open-zentra/foundation-bridge';
import { Priority, QueryMode } from '@open-zentra/foundation-bridge/types/pool';
```

#### Removed Re-exports

The following re-exports have been removed. Import from the canonical source:

| Old Import                            | New Import                                                               |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `types/pool.ts` → Priority, QueryMode | `constants` → PRIORITY, QUERY_MODE; types → PriorityLevel, QueryLockMode |
| `types/index.ts` → BridgeType         | `constants` → BRIDGE_TYPE; type → BridgeType                             |
| `wasm/pool/types.ts`                  | Deleted - use `types/pool.ts`                                            |
| `wasm/pool/index.ts` → error classes  | `errors/index.ts`                                                        |

---

## Contributing

### Code Style

- Use arrow functions for all function declarations
- Use `type` imports for type-only imports
- Constants: CAPITAL_SNAKE_CASE; types: PascalCase; type and const must not share the same name
- Follow const objects for enum-like values; derive PascalCase types from them
- Import branded types from `foundation-data-model`
- Import utilities from `foundation-utils`
- No re-exports - import from canonical source

### Pull Request Checklist

- [ ] Tests pass (`nx test foundation-bridge`)
- [ ] Linting passes (`nx lint foundation-bridge`)
- [ ] TypeScript compiles (`nx build foundation-bridge`)
- [ ] No circular dependencies
- [ ] Documentation updated

---

## License

MIT
