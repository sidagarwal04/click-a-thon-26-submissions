/**
 * Error exports
 *
 * NOTE: Foundation error utilities (FoundationError, isFoundationError, hasErrorCode, etc.)
 * should be imported directly from '@open-zentra/foundation-data-model'.
 *
 * NOTE: OpfsNotSupportedError should be imported directly from '@open-zentra/foundation-database'
 * since OPFS is fundamentally a database concern.
 *
 * @module errors
 */

// Base error class and type guard
export { BridgeError, isBridgeError } from './base-error';

// Bridge-owned query error
export { SqlValidationError } from './query-errors';

// Pool errors
export {
  PoolShutdownError,
  WorkerError,
  WorkerInitializationError,
  NoAvailableWorkersError,
  PoolCapacityError,
} from './pool-errors';

// Bridge and OPFS errors
export {
  BridgeNotInitializedError,
  BridgeInitializationError,
  OpfsNotFoundError,
  OpfsPermissionError,
  OpfsWriteError,
  ConfigurationError,
} from './bridge-errors';

// Type guards for all error types
export {
  // Query error type guards
  isQueryTimeoutError,
  isQueryCancelledError,
  isQueryExecutionError,
  isSqlValidationError,
  // Pool error type guards
  isPoolShutdownError,
  isWorkerError,
  isWorkerInitializationError,
  isNoAvailableWorkersError,
  isPoolCapacityError,
  // Bridge error type guards
  isBridgeNotInitializedError,
  isBridgeInitializationError,
  isOpfsNotFoundError,
  isOpfsPermissionError,
  isOpfsWriteError,
  isConfigurationError,
} from './type-guards';
