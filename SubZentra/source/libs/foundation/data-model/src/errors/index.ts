/**
 * Foundation Error Exports
 * @module errors
 */

// Error codes
export {
  FOUNDATION_ERROR_CODE,
  ERROR_CATEGORY,
  getErrorCategory,
  isRetryableErrorCode,
} from './error-codes';
export type { FoundationErrorCode, ErrorCategory } from './error-codes';

// Foundation error base class
export {
  FoundationError,
  GenericFoundationError,
  toFoundationError,
  isFoundationError,
  hasErrorCode,
  isErrorCategory,
} from './foundation-error';
export type { SerializedError, ErrorContext } from './foundation-error';

// Error callback interface
export {
  createErrorInfo,
  adaptLegacyCallback,
  adaptToLegacyCallback,
  noopErrorCallback,
  createConsoleErrorCallback,
  combineErrorCallbacks,
  filterByCategory,
  filterByCode,
} from './error-callback';
export type { ErrorInfo, FoundationErrorCallback, LegacyErrorCallback } from './error-callback';

// Shared query execution errors (used across bridge/query-engine/data-layer)
export {
  QueryTimeoutError,
  QueryCancelledError,
  QueryExecutionError,
  CANCELLATION_REASON,
} from './query-errors';
export type { CancellationReasonKind } from './query-errors';
