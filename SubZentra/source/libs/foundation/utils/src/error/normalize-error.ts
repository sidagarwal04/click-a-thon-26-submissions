/**
 * Error normalization utilities
 *
 * Provides utilities for normalizing unknown error values to Error instances.
 *
 * @module error/normalize-error
 */

/**
 * Helper to safely extract a string property from an unknown object.
 */
const getStringProp = (obj: object, key: string): string | undefined => {
  if (key in obj) {
    const value = (obj as Record<string, unknown>)[key];
    return typeof value === 'string' ? value : undefined;
  }
  return undefined;
};

/**
 * Normalize unknown error to Error instance
 *
 * Safely converts any thrown value to an Error object.
 * Handles strings, objects with message property, and other primitives.
 *
 * @param error - Unknown error value
 * @returns Normalized Error instance
 *
 * @example
 * ```typescript
 * try {
 *   throw 'string error';
 * } catch (e) {
 *   const error = normalizeError(e);
 *   console.log(error.message); // 'string error'
 * }
 * ```
 *
 * @example
 * ```typescript
 * try {
 *   throw { message: 'object error', code: 500 };
 * } catch (e) {
 *   const error = normalizeError(e);
 *   console.log(error.message); // 'object error'
 * }
 * ```
 */
export const normalizeError = (error: unknown): Error => {
  // Already an Error
  if (error instanceof Error) {
    return error;
  }

  // String error
  if (typeof error === 'string') {
    return new Error(error);
  }

  // Object with message property
  if (error && typeof error === 'object' && 'message' in error) {
    const message = String((error as Record<string, unknown>).message);
    const normalizedError = new Error(message);

    // Copy additional properties using safe property access
    const name = getStringProp(error, 'name');
    if (name) {
      normalizedError.name = name;
    }
    const stack = getStringProp(error, 'stack');
    if (stack) {
      normalizedError.stack = stack;
    }

    return normalizedError;
  }

  // Fallback: convert to string
  return new Error(String(error));
};

/**
 * Format error message with context prefix
 *
 * Creates a standardized error message format for logging.
 *
 * @param context - Context identifier (e.g., component name, function name)
 * @param message - Error message
 * @returns Formatted message string
 *
 * @example
 * ```typescript
 * formatErrorMessage('useDLCreate', 'Failed to create entity');
 * // '[useDLCreate] Failed to create entity'
 * ```
 */
export const formatErrorMessage = (context: string, message: string): string =>
  `[${context}] ${message}`;

/**
 * Extract error message from unknown error
 *
 * Safely extracts the message without creating a new Error object.
 *
 * @param error - Unknown error value
 * @returns Error message string
 */
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as Record<string, unknown>).message);
  }

  return String(error);
};

/**
 * Extract error name from unknown error
 *
 * @param error - Unknown error value
 * @returns Error name or 'Error' as default
 */
export const getErrorName = (error: unknown): string => {
  if (error instanceof Error) {
    return error.name;
  }

  if (error && typeof error === 'object') {
    const name = getStringProp(error, 'name');
    if (name) {
      return name;
    }
  }

  return 'Error';
};
