/**
 * WASM bridge exports
 * @module wasm
 */

export { WasmDuckDBBridge, type WasmDuckDBBridgeConfig } from './wasm-bridge';

export { createDuckDBInstance, type DuckDBInstance } from './duckdb-init';

// Worker Pool exports
export {
  // Factory functions
  createDuckDBPool,
  getDuckDBPool,
  resetDuckDBPool,
  type DuckDBPool,

  // Classes
  QueryCoordinator,
  WorkerPoolManager,
  WorkerInstance,
  PriorityQueue,
  TableLockManager,

  // Types (PascalCase)
  type QueryRequest,
  type PoolQueryResult,
  type PriorityLevel,
  type WorkerStatus,
  type WorkerInfo,
  type DuckDBPoolConfig,
  type PoolStatus,

  // Error types
  WorkerError,
  PoolShutdownError,
} from './pool';
