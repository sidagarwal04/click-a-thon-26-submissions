/**
 * @foundation/bridge - Internal Exports
 *
 * @internal
 * Internal exports for foundation library use only.
 * Not part of public API - may change without notice.
 *
 * These exports are used internally by the foundation layer but should not
 * be imported directly by application code. If you need functionality from
 * these modules, please use the public API instead.
 *
 * NOTE: Branded types (QueryId, WorkerId, SqlIdentifier, SqlTableName, Milliseconds, Timestamp)
 * should be imported directly from '@open-zentra/foundation-data-model'.
 *
 * @packageDocumentation
 */

// ============================================================================
// All Types (Internal Access)
// ============================================================================

export type {
  QueryOptions,
  ViewDefinition,
  TableInfo,
  ColumnInfo,
  QueryResult,
  DuckDBBridge,
  DuckDBBridgeStatus,
} from './types/bridge';

// Pool types - WORKER_STATUS is const (CAPITAL_SNAKE), WorkerStatus is type (PascalCase)
export { WORKER_STATUS } from './types/pool';
export type { WorkerStatus } from './types/pool';

export type {
  QueryRequest,
  QueryItem,
  PoolQueryResult,
  WorkerInfo,
  DuckDBPoolConfig,
  ResolvedPoolConfig,
  PoolStatus,
} from './types/pool';

// ============================================================================
// All Errors (Internal Access)
// ============================================================================

export { BridgeError } from './errors/base-error';

// Bridge-owned query error
export { SqlValidationError } from './errors/query-errors';

export {
  PoolShutdownError,
  WorkerError,
  WorkerInitializationError,
  NoAvailableWorkersError,
  PoolCapacityError,
} from './errors/pool-errors';

// NOTE: For OpfsNotSupportedError, import directly from '@open-zentra/foundation-database'
export {
  BridgeNotInitializedError,
  BridgeInitializationError,
  OpfsNotFoundError,
  OpfsPermissionError,
  OpfsWriteError,
  ConfigurationError,
} from './errors/bridge-errors';

// ============================================================================
// All Utils (Internal Access)
// ============================================================================

export {
  validateIdentifier,
  validateTableName,
  isValidIdentifier,
  quoteIdentifier,
  buildCreateViewSql,
  buildDropViewSql,
  escapeString,
  buildParameterizedSql,
  applyLimitOffset,
} from './utils/sql';

export { validatePoolConfig, validateRouterConfig, resolvePoolConfig } from './utils/validation';

export type { RouterConfigForValidation } from './utils/validation';

// NOTE: For async utilities (sleep, withTimeout), import directly from:
// '@open-zentra/foundation-utils'

// NOTE: For generic utilities, import directly from source packages:
// - From '@open-zentra/foundation-utils': deepFreeze, assert, assertDefined, isPositiveInteger, isNonNegative
// - From '@open-zentra/foundation-data-model': ValidationResult, ValidationResultData

// ============================================================================
// All Constants (Internal Access)
// ============================================================================

export { DEFAULTS, PRIORITY_VALUES, SQL, WORKER_MESSAGE_TYPES } from './constants';

export type { SqlReservedWord, WorkerMessageType } from './constants';

// Constants (CAPITAL_SNAKE) and types (PascalCase)
export {
  PRIORITY,
  QUERY_MODE,
  BRIDGE_TYPE,
  RUNTIME_ENVIRONMENT,
  STORAGE_STRATEGY,
} from './constants';
export type {
  PriorityLevel,
  QueryLockMode,
  BridgeType,
  RuntimeEnvironmentKind,
  StorageStrategyKind,
} from './constants';

// ============================================================================
// Environment Detection (Internal Access)
// ============================================================================

export { EnvironmentDetector } from './detection';

export type { EnvironmentCapabilities } from './detection';

// ============================================================================
// Worker Pool Internals
// ============================================================================

export {
  QueryCoordinator,
  WorkerPoolManager,
  WorkerInstance,
  PriorityQueue,
  TableLockManager,
} from './wasm/pool';

// ============================================================================
// WASM Bridge Internals
// ============================================================================

export { WasmDuckDBBridge, type WasmDuckDBBridgeConfig } from './wasm/wasm-bridge';

// ============================================================================
// Native Bridge Internals
// ============================================================================

export { ElectronDuckDBBridge, type ElectronDuckDBBridgeConfig } from './native/electron-bridge';
