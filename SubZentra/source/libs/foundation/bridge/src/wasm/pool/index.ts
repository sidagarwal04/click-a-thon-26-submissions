/**
 * DuckDB Worker Pool
 *
 * A multi-worker DuckDB-WASM pool with:
 * - Configurable number of workers
 * - Least-busy routing
 * - Priority queuing (high/normal/low)
 * - Table locking for shared OPFS access
 * - Query cancellation via AbortSignal
 * - Query timeouts
 *
 * NOTE: Import types from '../../types/pool' or '../../types'.
 * NOTE: Import errors from '../../errors'.
 * NOTE: Import constants from '../../constants'.
 *
 * @module wasm/pool
 */

// Core classes
export { QueryCoordinator } from './query-coordinator';
export { WorkerPoolManager } from './worker-pool';
export { WorkerInstance } from './worker-instance';
export { PriorityQueue } from './priority-queue';
export { TableLockManager } from './table-lock-manager';

// Factory
export { createDuckDBPool, getDuckDBPool, resetDuckDBPool, type DuckDBPool } from './factory';

// Types (re-exported for wasm/index and consumers)
export type {
  QueryRequest,
  PoolQueryResult,
  WorkerInfo,
  DuckDBPoolConfig,
  PoolStatus,
} from '../../types/pool';
export type { PriorityLevel } from '../../constants';
export { WORKER_STATUS } from '../../types/pool';
export type { WorkerStatus } from '../../types/pool';

// Errors
export { WorkerError, PoolShutdownError } from '../../errors';
