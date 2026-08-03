/**
 * DuckDB Worker Pool types
 *
 * Type definitions for the worker pool architecture including
 * query requests, worker status, pool configuration, and results.
 *
 * @module types/pool
 */

import type {
  Milliseconds,
  QueryId,
  Timestamp,
  WorkerId,
} from '@open-zentra/foundation-data-model';

import type { PriorityLevel, QueryLockMode } from '../constants';
import type { QueryResult } from './bridge';

// =============================================================================
// Query Types
// =============================================================================

/**
 * Query request submitted to the pool
 */
export interface QueryRequest {
  /** Unique query identifier (auto-generated if not provided) */
  readonly id?: QueryId;
  /** SQL query to execute */
  readonly sql: string;
  /** Tables accessed by this query (for locking) */
  readonly tables: readonly string[];
  /** Lock mode - READ allows concurrent access, WRITE is exclusive */
  readonly mode: QueryLockMode;
  /** Query priority (default: 'normal') */
  readonly priority?: PriorityLevel;
  /** Query timeout in milliseconds (overrides default) */
  readonly timeoutMs?: Milliseconds;
  /** AbortSignal for cancellation */
  readonly signal?: AbortSignal;
}

/**
 * Internal query item with metadata
 */
export interface QueryItem {
  /** Unique query identifier */
  readonly id: QueryId;
  /** The original request */
  readonly request: QueryRequest;
  /** When the query was submitted */
  readonly submittedAt: Timestamp;
  /** Promise resolution callback */
  resolve: (result: PoolQueryResult) => void;
  /** Promise rejection callback */
  reject: (error: Error) => void;
  /** Timeout handle if set */
  timeoutHandle?: ReturnType<typeof setTimeout>;
  /** Abort handler reference for cleanup */
  abortHandler?: () => void;
}

/**
 * Query result with pool metadata
 */
export interface PoolQueryResult<T extends Record<string, unknown> = Record<string, unknown>>
  extends QueryResult<T> {
  /** Query ID */
  readonly queryId: QueryId;
  /** Worker that executed the query */
  readonly workerId: WorkerId;
  /** Time spent waiting in queue (ms) */
  readonly queueTimeMs: number;
  /** Total time from submit to result (ms) */
  readonly totalTimeMs: number;
}

// =============================================================================
// Worker Types
// =============================================================================

/**
 * Worker status values (CAPITAL_SNAKE_CASE for constants)
 * - INITIALIZING: Worker is starting up
 * - IDLE: Worker is ready and waiting for queries
 * - BUSY: Worker is executing a query
 * - ERROR: Worker encountered an error
 * - SHUTDOWN: Worker is shutting down
 */
export const WORKER_STATUS = {
  INITIALIZING: 'initializing',
  IDLE: 'idle',
  BUSY: 'busy',
  ERROR: 'error',
  SHUTDOWN: 'shutdown',
} as const;

/** Worker status value type (PascalCase for types) */
export type WorkerStatus = (typeof WORKER_STATUS)[keyof typeof WORKER_STATUS];

/**
 * Worker instance information
 */
export interface WorkerInfo {
  /** Unique worker identifier */
  readonly id: WorkerId;
  /** Current status */
  readonly status: WorkerStatus;
  /** Number of queries in this worker's queue */
  readonly queueLength: number;
  /** Currently executing query ID (if busy) */
  readonly currentQueryId: QueryId | null;
  /** Total queries executed by this worker */
  readonly totalExecuted: number;
  /** When the worker was created */
  readonly createdAt: Timestamp;
  /** Last activity timestamp */
  readonly lastActivityAt: Timestamp;
  /** Last error if status is 'error' */
  readonly lastError?: string;
}

// =============================================================================
// Pool Configuration
// =============================================================================

/**
 * DuckDB Worker Pool configuration
 */
export interface DuckDBPoolConfig {
  /** Number of DuckDB worker instances */
  readonly workerCount?: number;
  /** Maximum queries queued per worker before overflow */
  readonly maxQueuePerWorker?: number;
  /** Maximum total active queries across all workers (default: 1000) */
  readonly maxActiveQueries?: number;
  /** Maximum items in the overflow queue before rejecting new queries (default: 500) */
  readonly maxOverflowQueueSize?: number;
  /** Default query timeout in ms */
  readonly defaultQueryTimeout?: Milliseconds;
  /** Worker initialization timeout in ms */
  readonly workerInitTimeout?: Milliseconds;
  /** Idle timeout before shutting down excess workers (optional) */
  readonly workerIdleTimeout?: Milliseconds | null;
  /** Enable table locking for OPFS coordination */
  readonly enableTableLocking?: boolean;
  /** Automatically restart failed workers */
  readonly restartFailedWorkers?: boolean;
  /** Enable debug logging */
  readonly debug?: boolean;
}

/**
 * Resolved configuration with all defaults applied
 */
export interface ResolvedPoolConfig {
  readonly workerCount: number;
  readonly maxQueuePerWorker: number;
  readonly maxActiveQueries: number;
  readonly maxOverflowQueueSize: number;
  readonly defaultQueryTimeout: Milliseconds;
  readonly workerInitTimeout: Milliseconds;
  readonly workerIdleTimeout: Milliseconds | null;
  readonly enableTableLocking: boolean;
  readonly restartFailedWorkers: boolean;
  readonly debug: boolean;
}

// =============================================================================
// Pool Status
// =============================================================================

/**
 * Overall pool status
 */
export interface PoolStatus {
  /** Whether the pool is initialized and ready */
  readonly ready: boolean;
  /** Whether the pool is shutting down */
  readonly shuttingDown: boolean;
  /** Worker statuses */
  readonly workers: readonly WorkerInfo[];
  /** Number of queries in global overflow queue */
  readonly globalQueueLength: number;
  /** Total queries executed since pool creation */
  readonly totalExecuted: number;
  /** Total queries currently pending (all queues) */
  readonly totalPending: number;
  /** Pool uptime in ms */
  readonly uptimeMs: number;
}

// =============================================================================
// Table Lock Types
// =============================================================================

/**
 * Read-only table lock status for external observation
 *
 * This is the public interface for checking lock state.
 * The internal mutable TableLock type is used only by TableLockManager.
 */
export interface TableLockStatus {
  /** Number of active readers */
  readonly readers: number;
  /** Whether a writer holds the lock */
  readonly writer: boolean;
  /** Number of pending readers waiting for the lock */
  readonly pendingReaders: number;
  /** Number of pending writers waiting for the lock */
  readonly pendingWriters: number;
}
