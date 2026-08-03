/**
 * Standardized Error Handling Utilities for Data Layer
 *
 * Provides consistent error handling patterns across all data-layer hooks.
 * Centralizes error logging and transformation for better debugging.
 *
 * This module builds on top of foundation-utils error utilities with
 * data-layer-specific features:
 * - Severity levels (WARN vs ERROR) for differentiated logging
 * - HOOK_CONTEXT const for domain-specific context identifiers
 * - Additional data context for richer error logs
 * - Returns normalized errors for chaining
 *
 * For generic error utilities (normalizeError, formatErrorMessage,
 * isErrorType, isAbortError, isNetworkError), import directly from
 * @open-zentra/foundation-utils
 *
 * @module utils/error-handler
 */

import {
  createLogger,
  formatErrorMessage,
  normalizeError,
} from '@open-zentra/foundation-utils';

// =============================================================================
// CONST PATTERNS (replaces union types)
// =============================================================================

/**
 * Error severity levels
 *
 * @example
 * ```ts
 * handleError(err, { context: HOOK_CONTEXT.USE_DL_GET, severity: ERROR_SEVERITY.ERROR });
 * ```
 */
export const ERROR_SEVERITY = {
  WARN: 'warn',
  ERROR: 'error',
} as const;

export type ErrorSeverityValue = (typeof ERROR_SEVERITY)[keyof typeof ERROR_SEVERITY];

/**
 * Hook context identifiers for error messages
 *
 * @example
 * ```ts
 * const handleGetError = createScopedErrorHandler(HOOK_CONTEXT.USE_DL_GET);
 * ```
 */
export const HOOK_CONTEXT = {
  USE_DL_GET: 'useDLGet',
  USE_DL_CREATE: 'useDLCreate',
  USE_DL_UPDATE: 'useDLUpdate',
  USE_DL_DELETE: 'useDLDelete',
  USE_DL_ANALYTICS: 'useDLAnalytics',
  USE_DL_ANALYTICS_MUTATION: 'useDLAnalyticsMutation',
  USE_SYNC_STATUS: 'useSyncStatus',
  USE_CONFLICT_RESOLUTION: 'useConflictResolution',
  DATA_LAYER_PROVIDER: 'DataLayerProvider',
} as const;

export type HookContextValue = (typeof HOOK_CONTEXT)[keyof typeof HOOK_CONTEXT];

/**
 * Module-level logger for error handling.
 * Always outputs at 'warn' level so warnings and errors are visible.
 */
const errorLogger = createLogger('DataLayer', { level: 'warn' });

// =============================================================================
// ERROR HANDLER OPTIONS
// =============================================================================

/**
 * Error handler options
 */
export interface ErrorHandlerOptions {
  /** Context where the error occurred */
  readonly context: HookContextValue | string;
  /** Error severity level (default: WARN) */
  readonly severity?: ErrorSeverityValue;
  /** Additional context data to include in logs */
  readonly data?: Readonly<Record<string, unknown>>;
  /** Whether to rethrow the error after handling */
  readonly rethrow?: boolean;
}

// =============================================================================
// ERROR HANDLING FUNCTIONS
// =============================================================================

/**
 * Handle error with standardized logging
 *
 * Logs errors with consistent formatting and optional data.
 * Can optionally rethrow the error after logging.
 *
 * @param error - Error to handle
 * @param options - Error handling options
 * @returns The normalized error (for chaining or inspection)
 *
 * @example
 * ```ts
 * // Log a warning
 * handleError(err, { context: HOOK_CONTEXT.USE_DL_GET });
 *
 * // Log an error with additional data
 * handleError(err, {
 *   context: HOOK_CONTEXT.USE_DL_CREATE,
 *   severity: ERROR_SEVERITY.ERROR,
 *   data: { table: 'users', entityId: '123' }
 * });
 *
 * // Log and rethrow
 * handleError(err, { context: HOOK_CONTEXT.USE_DL_DELETE, rethrow: true });
 * ```
 */
export const handleError = (error: unknown, options: ErrorHandlerOptions): Error => {
  const { context, severity = ERROR_SEVERITY.WARN, data, rethrow = false } = options;

  const normalizedError = normalizeError(error);
  const message = formatErrorMessage(context, normalizedError.message);

  // Log based on severity using structured logger
  if (severity === ERROR_SEVERITY.ERROR) {
    if (data) {
      errorLogger.error(message, data, normalizedError);
    } else {
      errorLogger.error(message, normalizedError);
    }
  } else {
    if (data) {
      errorLogger.warn(message, data);
    } else {
      errorLogger.warn(message);
    }
  }

  // Optionally rethrow
  if (rethrow) {
    throw normalizedError;
  }

  return normalizedError;
};

/**
 * Create a scoped error handler for a specific context
 *
 * Returns a pre-configured error handler for a specific hook or component.
 * Reduces boilerplate by pre-filling the context.
 *
 * @param context - Default context for all errors
 * @returns Scoped error handler function
 *
 * @example
 * ```ts
 * // Create a scoped handler for a hook
 * const handleHookError = createScopedErrorHandler(HOOK_CONTEXT.USE_DL_CREATE);
 *
 * // Use it throughout the hook
 * try {
 *   await someOperation();
 * } catch (err) {
 *   handleHookError(err, { severity: ERROR_SEVERITY.ERROR });
 * }
 * ```
 */
export const createScopedErrorHandler =
  (context: HookContextValue | string) =>
  (error: unknown, options?: Omit<ErrorHandlerOptions, 'context'>): Error =>
    handleError(error, { ...options, context });

/**
 * Safe async error wrapper
 *
 * Wraps an async function to catch and handle errors.
 * Useful for fire-and-forget operations where errors should be logged but not thrown.
 *
 * @param fn - Async function to wrap
 * @param options - Error handling options
 * @returns Wrapped async function that catches errors
 *
 * @example
 * ```ts
 * // Wrap a database operation
 * const safePersist = safeAsync(
 *   async () => await database.queries.set(entry),
 *   { context: HOOK_CONTEXT.USE_DL_GET }
 * );
 *
 * // Call it - errors are logged but not thrown
 * await safePersist();
 * ```
 */
export const safeAsync =
  <T>(fn: () => Promise<T>, options: ErrorHandlerOptions): (() => Promise<T | undefined>) =>
  async () => {
    try {
      return await fn();
    } catch (error) {
      handleError(error, options);
      return undefined;
    }
  };

/**
 * Create a try-catch wrapper that handles errors
 *
 * Similar to safeAsync but can also return a default value on error.
 *
 * @param fn - Async function to execute
 * @param options - Error handling options
 * @param defaultValue - Optional default value to return on error
 * @returns The result or default value
 *
 * @example
 * ```ts
 * const data = await tryCatchAsync(
 *   async () => await fetchData(),
 *   { context: HOOK_CONTEXT.USE_DL_GET },
 *   null // Return null on error
 * );
 * ```
 */
export const tryCatchAsync = async <T>(
  fn: () => Promise<T>,
  options: ErrorHandlerOptions,
  defaultValue?: T,
): Promise<T | undefined> => {
  try {
    return await fn();
  } catch (error) {
    handleError(error, options);
    return defaultValue;
  }
};
