/**
 * Error type guard utilities
 *
 * Provides type guards for identifying specific error types.
 * Uses structural (duck-type) checks as the primary guard so that errors
 * originating from Web Workers or other realms are detected correctly.
 * `instanceof` is used as a secondary check where available.
 *
 * @module error/error-guards
 */

/**
 * Structural check for error-like objects.
 *
 * Works across JavaScript realms (Web Workers, iframes) where
 * `instanceof Error` returns false because each realm has its own
 * `Error` constructor.
 */
export const isErrorLike = (
  value: unknown,
): value is { message: string; name: string; stack?: string } =>
  typeof value === 'object' &&
  value !== null &&
  'message' in value &&
  typeof (value as Record<string, unknown>).message === 'string' &&
  'name' in value &&
  typeof (value as Record<string, unknown>).name === 'string';

/**
 * Check if an error is of a specific type by name
 *
 * @param error - Error to check
 * @param name - Error name to match
 * @returns True if error matches the name
 *
 * @example
 * ```typescript
 * try {
 *   await fetch('/api');
 * } catch (e) {
 *   if (isErrorType(e, 'AbortError')) {
 *     // Handle abort
 *   }
 * }
 * ```
 */
export const isErrorType = (error: unknown, name: string): boolean => {
  return isErrorLike(error) && error.name === name;
};

/**
 * Check if an error is an AbortError (from AbortController)
 *
 * @param error - Error to check
 * @returns True if error is an abort error
 *
 * @example
 * ```typescript
 * const controller = new AbortController();
 * controller.abort();
 *
 * try {
 *   await fetch('/api', { signal: controller.signal });
 * } catch (e) {
 *   if (isAbortError(e)) {
 *     // Request was cancelled - not a real error
 *     return;
 *   }
 *   throw e;
 * }
 * ```
 */
export const isAbortError = (error: unknown): boolean => {
  return isErrorType(error, 'AbortError');
};

/**
 * Network error detection patterns
 *
 * Note: 'timeout' and 'etimedout' are intentionally excluded here
 * so that timeout errors are detected by `isTimeoutError` instead
 * of being swallowed by `isNetworkError`.
 */
const NETWORK_ERROR_PATTERNS: readonly string[] = [
  'network',
  'fetch',
  'failed to fetch',
  'networkerror',
  'connection',
  'offline',
  'econnrefused',
  'enotfound',
  'socket hang up',
] as const;

/**
 * Check if an error is a network error
 *
 * Detects common network-related errors based on message patterns.
 *
 * @param error - Error to check
 * @returns True if error appears to be network-related
 *
 * @example
 * ```typescript
 * try {
 *   await fetch('/api');
 * } catch (e) {
 *   if (isNetworkError(e)) {
 *     // Show offline message
 *     showNotification('You appear to be offline');
 *   }
 * }
 * ```
 */
export const isNetworkError = (error: unknown): boolean => {
  if (!isErrorLike(error)) return false;

  const message = error.message.toLowerCase();
  return NETWORK_ERROR_PATTERNS.some((pattern) => message.includes(pattern));
};

/**
 * Check if an error is a timeout error
 *
 * @param error - Error to check
 * @returns True if error is a timeout error
 */
export const isTimeoutError = (error: unknown): boolean => {
  if (!isErrorLike(error)) return false;

  const message = error.message.toLowerCase();
  return (
    error.name === 'TimeoutError' || message.includes('timeout') || message.includes('timed out')
  );
};

/**
 * Check if an error is a type error (usually programming mistake)
 *
 * @param error - Error to check
 * @returns True if error is a TypeError
 */
export const isTypeError = (error: unknown): error is TypeError => {
  return error instanceof TypeError || (isErrorLike(error) && error.name === 'TypeError');
};

/**
 * Check if an error is a syntax error
 *
 * @param error - Error to check
 * @returns True if error is a SyntaxError
 */
export const isSyntaxError = (error: unknown): error is SyntaxError => {
  return error instanceof SyntaxError || (isErrorLike(error) && error.name === 'SyntaxError');
};

/**
 * Check if an error is a range error
 *
 * @param error - Error to check
 * @returns True if error is a RangeError
 */
export const isRangeError = (error: unknown): error is RangeError => {
  return error instanceof RangeError || (isErrorLike(error) && error.name === 'RangeError');
};

/**
 * Check if error has a specific error code
 *
 * @param error - Error to check
 * @param code - Error code to match
 * @returns True if error has matching code
 */
export const hasErrorCode = (error: unknown, code: string | number): boolean => {
  if (!isErrorLike(error)) return false;

  return 'code' in error && (error as Record<string, unknown>).code === code;
};

/**
 * Check if HTTP status code indicates a retriable error
 *
 * @param status - HTTP status code
 * @returns True if the error is potentially retriable
 */
export const isRetriableHttpStatus = (status: number): boolean => {
  return (
    status >= 500 || // Server errors
    status === 408 || // Request Timeout
    status === 429 || // Too Many Requests
    status === 0 // Network error
  );
};
