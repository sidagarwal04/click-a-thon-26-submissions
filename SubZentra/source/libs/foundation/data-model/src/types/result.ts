/**
 * Result type for type-safe error handling
 *
 * Provides a discriminated union for operations that can fail,
 * enabling explicit error handling without exceptions.
 *
 * @module types/result
 */

// =============================================================================
// Result Type
// =============================================================================

/**
 * Result type - represents either success or failure
 *
 * A discriminated union that forces explicit handling of both success and failure cases.
 * Inspired by Rust's Result type.
 *
 * @template T - The success value type
 * @template E - The error type (must extend Error)
 *
 * @example
 * ```typescript
 * async function divide(a: number, b: number): Promise<Result<number, Error>> {
 *   if (b === 0) {
 *     return Result.err(new Error('Division by zero'));
 *   }
 *   return Result.ok(a / b);
 * }
 *
 * const result = await divide(10, 2);
 * if (result.ok) {
 *   console.log('Result:', result.value); // 5
 * } else {
 *   console.error('Error:', result.error.message);
 * }
 * ```
 */
export type Result<T, E extends Error = Error> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: E };

// =============================================================================
// Result Utilities
// =============================================================================

/**
 * Result constructor and utility functions
 *
 * Provides functional utilities for working with Result types.
 */
export const Result = {
  /**
   * Create a successful result
   *
   * @param value - The success value
   * @returns A successful Result containing the value
   *
   * @example
   * ```typescript
   * const result = Result.ok(42);
   * // { ok: true, value: 42 }
   * ```
   */
  ok: <T>(value: T): Result<T, never> => ({ ok: true, value }),

  /**
   * Create a failure result
   *
   * @param error - The error value
   * @returns A failed Result containing the error
   *
   * @example
   * ```typescript
   * const result = Result.err(new Error('Something went wrong'));
   * // { ok: false, error: Error('Something went wrong') }
   * ```
   */
  err: <E extends Error>(error: E): Result<never, E> => ({ ok: false, error }),

  /**
   * Wrap a promise to return Result instead of throwing
   *
   * @param promise - The promise to wrap
   * @param errorMapper - Optional function to transform caught errors
   * @returns A Promise that resolves to a Result
   *
   * @example
   * ```typescript
   * const result = await Result.fromPromise(
   *   fetch('/api/data'),
   *   (e) => new NetworkError(e)
   * );
   * ```
   */
  fromPromise: async <T, E extends Error = Error>(
    promise: Promise<T>,
    errorMapper?: (e: unknown) => E,
  ): Promise<Result<T, E>> => {
    try {
      const value = await promise;
      return { ok: true, value };
    } catch (e) {
      const error = errorMapper
        ? errorMapper(e)
        : ((e instanceof Error ? e : new Error(String(e))) as E);
      return { ok: false, error };
    }
  },

  /**
   * Unwrap Result, throwing if error
   *
   * @param result - The Result to unwrap
   * @returns The success value
   * @throws The error if Result is a failure
   *
   * @example
   * ```typescript
   * const value = Result.unwrap(result); // throws if not ok
   * ```
   */
  unwrap: <T, E extends Error>(result: Result<T, E>): T => {
    if (result.ok) return result.value;
    throw result.error;
  },

  /**
   * Unwrap Result with default value on error
   *
   * @param result - The Result to unwrap
   * @param defaultValue - Value to return if Result is a failure
   * @returns The success value or the default value
   *
   * @example
   * ```typescript
   * const value = Result.unwrapOr(result, 0);
   * ```
   */
  unwrapOr: <T, E extends Error>(result: Result<T, E>, defaultValue: T): T => {
    if (result.ok) return result.value;
    return defaultValue;
  },

  /**
   * Map successful value to a new value
   *
   * @param result - The Result to map
   * @param fn - Function to transform the success value
   * @returns A new Result with the transformed value
   *
   * @example
   * ```typescript
   * const doubled = Result.map(result, (x) => x * 2);
   * ```
   */
  map: <T, U, E extends Error>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> => {
    if (result.ok) return { ok: true, value: fn(result.value) };
    return result;
  },

  /**
   * Map error to a new error
   *
   * @param result - The Result to map
   * @param fn - Function to transform the error
   * @returns A new Result with the transformed error
   *
   * @example
   * ```typescript
   * const mapped = Result.mapError(result, (e) => new CustomError(e.message));
   * ```
   */
  mapError: <T, E extends Error, F extends Error>(
    result: Result<T, E>,
    fn: (error: E) => F,
  ): Result<T, F> => {
    if (result.ok) return result;
    return { ok: false, error: fn(result.error) };
  },

  /**
   * Chain Result-returning operations (flatMap/bind)
   *
   * @param result - The Result to chain
   * @param fn - Function that returns a new Result
   * @returns The Result from the function, or the original error
   *
   * @example
   * ```typescript
   * const result = Result.flatMap(parseResult, validate);
   * ```
   */
  flatMap: <T, U, E extends Error>(
    result: Result<T, E>,
    fn: (value: T) => Result<U, E>,
  ): Result<U, E> => {
    if (result.ok) return fn(result.value);
    return result;
  },

  /**
   * Check if result is successful (type guard)
   *
   * @param result - The Result to check
   * @returns True if Result is successful
   *
   * @example
   * ```typescript
   * if (Result.isOk(result)) {
   *   console.log(result.value); // TypeScript knows value exists
   * }
   * ```
   */
  isOk: <T, E extends Error>(result: Result<T, E>): result is { ok: true; value: T } => {
    return result.ok;
  },

  /**
   * Check if result is an error (type guard)
   *
   * @param result - The Result to check
   * @returns True if Result is a failure
   *
   * @example
   * ```typescript
   * if (Result.isErr(result)) {
   *   console.error(result.error); // TypeScript knows error exists
   * }
   * ```
   */
  isErr: <T, E extends Error>(result: Result<T, E>): result is { ok: false; error: E } => {
    return !result.ok;
  },

  /**
   * Execute callback on success (side effect)
   *
   * @param result - The Result to tap
   * @param fn - Function to execute on success
   * @returns The original Result unchanged
   *
   * @example
   * ```typescript
   * const result = Result.tap(parseResult, (value) => console.log('Parsed:', value));
   * ```
   */
  tap: <T, E extends Error>(result: Result<T, E>, fn: (value: T) => void): Result<T, E> => {
    if (result.ok) fn(result.value);
    return result;
  },

  /**
   * Execute callback on error (side effect)
   *
   * @param result - The Result to tap
   * @param fn - Function to execute on error
   * @returns The original Result unchanged
   *
   * @example
   * ```typescript
   * const result = Result.tapError(parseResult, (err) => console.error('Error:', err));
   * ```
   */
  tapError: <T, E extends Error>(result: Result<T, E>, fn: (error: E) => void): Result<T, E> => {
    if (!result.ok) fn(result.error);
    return result;
  },
};
