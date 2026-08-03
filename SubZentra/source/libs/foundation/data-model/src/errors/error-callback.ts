/**
 * Error Callback Interface
 *
 * Standardized callback interface for error handling across foundation libraries.
 * Provides consistent error reporting with structured error information.
 *
 * @module errors/error-callback
 */

import type { ErrorCategory, FoundationErrorCode } from './error-codes';
import type { ErrorContext } from './foundation-error';
import { toFoundationError, type FoundationError } from './foundation-error';

// =============================================================================
// Types
// =============================================================================

/**
 * Structured error information passed to error callbacks
 */
export interface ErrorInfo {
  /** The error instance */
  readonly error: FoundationError;
  /** Error code for programmatic handling */
  readonly code: FoundationErrorCode;
  /** Error category */
  readonly category: ErrorCategory;
  /** Whether the error is retryable */
  readonly isRetryable: boolean;
  /** Whether the error should be reported to error tracking */
  readonly shouldReport: boolean;
  /** Source component that generated the error */
  readonly source: string;
  /** Timestamp when the error occurred */
  readonly timestamp: number;
  /** Error context metadata */
  readonly context: Readonly<ErrorContext>;
}

/**
 * Foundation error callback type
 *
 * Used for centralized error handling in foundation libraries.
 * Can return void or a Promise for async error handling.
 */
export type FoundationErrorCallback = (info: ErrorInfo) => void | Promise<void>;

/**
 * Simple error callback type for components that don't need structured error info.
 *
 * For richer error context, use `FoundationErrorCallback` which receives `ErrorInfo`.
 */
export type LegacyErrorCallback = (error: Error, context?: string) => void;

// =============================================================================
// Utilities
// =============================================================================

/**
 * Create ErrorInfo from a FoundationError
 *
 * @param error - The foundation error
 * @param source - Source component name
 * @returns Structured error information
 */
export function createErrorInfo(error: FoundationError, source: string): ErrorInfo {
  return {
    error,
    code: error.code,
    category: error.category,
    isRetryable: error.isRetryable,
    shouldReport: error.shouldReport,
    source,
    timestamp: error.timestamp,
    context: error.context,
  };
}

/**
 * Adapt a legacy error callback to the new FoundationErrorCallback interface
 *
 * @param legacyCallback - Legacy callback function
 * @returns Adapted FoundationErrorCallback
 *
 * @example
 * ```typescript
 * const legacyHandler = (error: Error, context?: string) => console.error(context, error);
 * const newHandler = adaptLegacyCallback(legacyHandler);
 * ```
 */
export function adaptLegacyCallback(legacyCallback: LegacyErrorCallback): FoundationErrorCallback {
  return (info: ErrorInfo) => {
    const context = info.source || info.context.operation || 'unknown';
    legacyCallback(info.error, context);
  };
}

/**
 * Adapt a FoundationErrorCallback to a legacy callback
 *
 * @param callback - Foundation callback function
 * @param source - Default source name
 * @returns Adapted legacy callback
 */
export function adaptToLegacyCallback(
  callback: FoundationErrorCallback,
  source: string,
): LegacyErrorCallback {
  return (error: Error, context?: string) => {
    const foundationError = toFoundationError(error, undefined, {
      source,
      operation: context,
    });

    void callback(createErrorInfo(foundationError, context ?? source));
  };
}

/**
 * Create a no-op error callback (for testing or when errors should be ignored)
 */
export const noopErrorCallback: FoundationErrorCallback = () => {
  // Intentionally empty
};

/**
 * Create an error callback that logs to console
 *
 * @param options - Logging options
 * @returns A console-logging error callback
 */
export function createConsoleErrorCallback(options?: {
  /** Only log errors that should be reported */
  onlyReportable?: boolean;
  /** Include stack trace in output */
  includeStack?: boolean;
}): FoundationErrorCallback {
  return (info: ErrorInfo) => {
    if (options?.onlyReportable && !info.shouldReport) {
      return;
    }

    const logData: Record<string, unknown> = {
      code: info.code,
      category: info.category,
      source: info.source,
      isRetryable: info.isRetryable,
      context: info.context,
    };

    if (options?.includeStack) {
      logData.stack = info.error.stack;
    }

    console.error(`[${info.code}] ${info.error.message}`, logData);
  };
}

/**
 * Combine multiple error callbacks into one
 *
 * @param callbacks - Array of callbacks to combine
 * @returns Combined callback that calls all provided callbacks
 */
export function combineErrorCallbacks(
  ...callbacks: FoundationErrorCallback[]
): FoundationErrorCallback {
  return async (info: ErrorInfo) => {
    for (const callback of callbacks) {
      try {
        await callback(info);
      } catch (error) {
        // Log but don't throw - error callbacks shouldn't break the main flow
        console.error('Error in error callback:', error);
      }
    }
  };
}

/**
 * Create an error callback that filters by category
 *
 * @param categories - Categories to handle
 * @param callback - Callback to invoke for matching errors
 * @returns Filtered error callback
 */
export function filterByCategory(
  categories: ErrorCategory[],
  callback: FoundationErrorCallback,
): FoundationErrorCallback {
  return (info: ErrorInfo) => {
    if (categories.includes(info.category)) {
      return callback(info);
    }
  };
}

/**
 * Create an error callback that filters by code
 *
 * @param codes - Error codes to handle
 * @param callback - Callback to invoke for matching errors
 * @returns Filtered error callback
 */
export function filterByCode(
  codes: FoundationErrorCode[],
  callback: FoundationErrorCallback,
): FoundationErrorCallback {
  return (info: ErrorInfo) => {
    if (codes.includes(info.code)) {
      return callback(info);
    }
  };
}
