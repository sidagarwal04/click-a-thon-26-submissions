/**
 * Type guards for bridge errors
 *
 * Provides type narrowing functions for all bridge error types.
 *
 * @module errors/type-guards
 */

import {
  QueryCancelledError,
  QueryExecutionError,
  QueryTimeoutError,
} from '@open-zentra/foundation-data-model';

import {
  BridgeInitializationError,
  BridgeNotInitializedError,
  ConfigurationError,
  OpfsNotFoundError,
  OpfsPermissionError,
  OpfsWriteError,
} from './bridge-errors';
import {
  NoAvailableWorkersError,
  PoolCapacityError,
  PoolShutdownError,
  WorkerError,
  WorkerInitializationError,
} from './pool-errors';
import { SqlValidationError } from './query-errors';

// NOTE: OpfsNotSupportedError and isOpfsNotSupportedError - import from '@open-zentra/foundation-database'

// =============================================================================
// Query Error Type Guards
// =============================================================================

/**
 * Type guard to check if an error is a QueryTimeoutError
 */
export const isQueryTimeoutError = (error: unknown): error is QueryTimeoutError =>
  error instanceof QueryTimeoutError;

/**
 * Type guard to check if an error is a QueryCancelledError
 */
export const isQueryCancelledError = (error: unknown): error is QueryCancelledError =>
  error instanceof QueryCancelledError;

/**
 * Type guard to check if an error is a QueryExecutionError
 */
export const isQueryExecutionError = (error: unknown): error is QueryExecutionError =>
  error instanceof QueryExecutionError;

/**
 * Type guard to check if an error is a SqlValidationError
 */
export const isSqlValidationError = (error: unknown): error is SqlValidationError =>
  error instanceof SqlValidationError;

// =============================================================================
// Pool Error Type Guards
// =============================================================================

/**
 * Type guard to check if an error is a PoolShutdownError
 */
export const isPoolShutdownError = (error: unknown): error is PoolShutdownError =>
  error instanceof PoolShutdownError;

/**
 * Type guard to check if an error is a WorkerError
 */
export const isWorkerError = (error: unknown): error is WorkerError => error instanceof WorkerError;

/**
 * Type guard to check if an error is a WorkerInitializationError
 */
export const isWorkerInitializationError = (error: unknown): error is WorkerInitializationError =>
  error instanceof WorkerInitializationError;

/**
 * Type guard to check if an error is a NoAvailableWorkersError
 */
export const isNoAvailableWorkersError = (error: unknown): error is NoAvailableWorkersError =>
  error instanceof NoAvailableWorkersError;

/**
 * Type guard to check if an error is a PoolCapacityError
 */
export const isPoolCapacityError = (error: unknown): error is PoolCapacityError =>
  error instanceof PoolCapacityError;

// =============================================================================
// Bridge Error Type Guards
// =============================================================================

/**
 * Type guard to check if an error is a BridgeNotInitializedError
 */
export const isBridgeNotInitializedError = (error: unknown): error is BridgeNotInitializedError =>
  error instanceof BridgeNotInitializedError;

/**
 * Type guard to check if an error is a BridgeInitializationError
 */
export const isBridgeInitializationError = (error: unknown): error is BridgeInitializationError =>
  error instanceof BridgeInitializationError;

/**
 * Type guard to check if an error is an OpfsNotFoundError
 */
export const isOpfsNotFoundError = (error: unknown): error is OpfsNotFoundError =>
  error instanceof OpfsNotFoundError;

/**
 * Type guard to check if an error is an OpfsPermissionError
 */
export const isOpfsPermissionError = (error: unknown): error is OpfsPermissionError =>
  error instanceof OpfsPermissionError;

/**
 * Type guard to check if an error is an OpfsWriteError
 */
export const isOpfsWriteError = (error: unknown): error is OpfsWriteError =>
  error instanceof OpfsWriteError;

/**
 * Type guard to check if an error is a ConfigurationError
 */
export const isConfigurationError = (error: unknown): error is ConfigurationError =>
  error instanceof ConfigurationError;
