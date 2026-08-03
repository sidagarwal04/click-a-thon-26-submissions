/**
 * Foundation Error Base Class
 *
 * Abstract base class for all foundation library errors.
 * Provides structured error information with code, category, context, and serialization.
 *
 * @module errors/foundation-error
 */

import { Timestamp } from '../types/branded';
import {
  ERROR_CATEGORY,
  FOUNDATION_ERROR_CODE,
  getErrorCategory,
  isRetryableErrorCode,
  type ErrorCategory,
  type FoundationErrorCode,
} from './error-codes';

// =============================================================================
// Types
// =============================================================================

/**
 * Serialized error format for logging and transport
 */
export interface SerializedError {
  name: string;
  code: FoundationErrorCode;
  category: ErrorCategory;
  message: string;
  timestamp: number;
  context: Record<string, unknown>;
  isRetryable: boolean;
  cause?: {
    name: string;
    message: string;
    stack?: string;
  };
  stack?: string;
}

/**
 * Error context - additional metadata about the error
 */
export interface ErrorContext {
  /** Source component that generated the error */
  source?: string;
  /** Operation that was being performed */
  operation?: string;
  /** Entity ID involved (if any) */
  entityId?: string;
  /** Table name involved (if any) */
  tableName?: string;
  /** Query ID (if any) */
  queryId?: string;
  /** Mutation ID (if any) */
  mutationId?: string;
  /** Worker ID (if any) */
  workerId?: string;
  /** Duration of operation before failure (ms) */
  durationMs?: number;
  /** Number of retry attempts */
  retryCount?: number;
  /** Additional custom context */
  [key: string]: unknown;
}

// =============================================================================
// Foundation Error Base Class
// =============================================================================

/**
 * Abstract base class for all foundation library errors
 *
 * All custom errors in foundation libraries should extend this class
 * to ensure consistent error handling, logging, and categorization.
 *
 * @example
 * ```typescript
 * class QueryTimeoutError extends FoundationError {
 *   readonly code = FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT;
 *
 *   constructor(queryId: string, timeoutMs: number, cause?: Error) {
 *     super(`Query ${queryId} timed out after ${timeoutMs}ms`, { queryId, timeoutMs }, cause);
 *   }
 * }
 * ```
 */
export abstract class FoundationError extends Error {
  /**
   * Unique error code for programmatic handling
   */
  abstract readonly code: FoundationErrorCode;

  /**
   * Timestamp when the error occurred
   */
  readonly timestamp: Timestamp;

  /**
   * Additional context about the error
   */
  readonly context: Readonly<ErrorContext>;

  /**
   * Original error that caused this error
   */
  override readonly cause?: Error;

  /**
   * Create a new FoundationError
   *
   * @param message - Human-readable error message
   * @param context - Additional context metadata
   * @param cause - Original error that caused this error
   */
  constructor(message: string, context: ErrorContext = {}, cause?: Error) {
    super(message);
    this.name = this.constructor.name;
    this.timestamp = Timestamp.now();
    this.context = Object.freeze({ ...context });
    this.cause = cause;

    // Maintains proper stack trace in V8 engines (Node, Chrome)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  /**
   * Get the error category
   */
  get category(): ErrorCategory {
    return getErrorCategory(this.code);
  }

  /**
   * Check if this error is retryable
   */
  get isRetryable(): boolean {
    return isRetryableErrorCode(this.code);
  }

  /**
   * Check if this error should be reported to error tracking
   */
  get shouldReport(): boolean {
    // Don't report user input errors or cancelled operations
    if (this.category === ERROR_CATEGORY.USER_INPUT) return false;
    if (this.code === FOUNDATION_ERROR_CODE.BRIDGE_QUERY_CANCELLED) return false;
    return true;
  }

  /**
   * Serialize error to JSON for logging
   */
  toJSON(): SerializedError {
    return {
      name: this.name,
      code: this.code,
      category: this.category,
      message: this.message,
      timestamp: this.timestamp,
      context: { ...this.context },
      isRetryable: this.isRetryable,
      cause: this.cause
        ? {
            name: this.cause.name,
            message: this.cause.message,
            stack: this.cause.stack,
          }
        : undefined,
      stack: this.stack,
    };
  }

  /**
   * Get a formatted string representation
   */
  override toString(): string {
    const contextStr =
      Object.keys(this.context).length > 0 ? ` [${JSON.stringify(this.context)}]` : '';
    return `${this.name} [${this.code}]: ${this.message}${contextStr}`;
  }

  /**
   * Create error with additional context
   *
   * @param additionalContext - Additional context to merge
   * @returns A new error instance with merged context
   */
  withContext(additionalContext: ErrorContext): this {
    // Create a new instance with the same code and merged context
    const Constructor = this.constructor as new (
      message: string,
      context: ErrorContext,
      cause?: Error,
    ) => this;
    return new Constructor(this.message, { ...this.context, ...additionalContext }, this.cause);
  }
}

// =============================================================================
// Generic Foundation Error
// =============================================================================

/**
 * Generic foundation error for cases where a specific error class isn't needed
 */
export class GenericFoundationError extends FoundationError {
  readonly code: FoundationErrorCode;

  constructor(
    code: FoundationErrorCode,
    message: string,
    context: ErrorContext = {},
    cause?: Error,
  ) {
    super(message, context, cause);
    this.code = code;
  }
}

// =============================================================================
// Error Factory Utilities
// =============================================================================

/**
 * Create a FoundationError from an unknown error
 *
 * @param error - Unknown error value
 * @param fallbackCode - Error code to use if unknown
 * @param context - Additional context
 * @returns A FoundationError instance
 */
export function toFoundationError(
  error: unknown,
  fallbackCode: FoundationErrorCode = FOUNDATION_ERROR_CODE.INTERNAL_ERROR,
  context: ErrorContext = {},
): FoundationError {
  // Already a FoundationError
  if (error instanceof FoundationError) {
    return context && Object.keys(context).length > 0 ? error.withContext(context) : error;
  }

  // Standard Error
  if (error instanceof Error) {
    return new GenericFoundationError(fallbackCode, error.message, context, error);
  }

  // String error
  if (typeof error === 'string') {
    return new GenericFoundationError(fallbackCode, error, context);
  }

  // Unknown error
  return new GenericFoundationError(fallbackCode, String(error), context);
}

/**
 * Check if an error is a FoundationError
 *
 * @param error - Error to check
 * @returns True if error is a FoundationError
 */
export function isFoundationError(error: unknown): error is FoundationError {
  return error instanceof FoundationError;
}

/**
 * Check if an error has a specific error code
 *
 * @param error - Error to check
 * @param code - Error code to check for
 * @returns True if error has the specified code
 */
export function hasErrorCode(error: unknown, code: FoundationErrorCode): error is FoundationError {
  return isFoundationError(error) && error.code === code;
}

/**
 * Check if an error is in a specific category
 *
 * @param error - Error to check
 * @param category - Category to check for
 * @returns True if error is in the specified category
 */
export function isErrorCategory(error: unknown, category: ErrorCategory): error is FoundationError {
  return isFoundationError(error) && error.category === category;
}
