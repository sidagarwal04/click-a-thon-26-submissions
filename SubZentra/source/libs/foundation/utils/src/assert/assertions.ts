/**
 * Assertion utilities
 *
 * Provides type-safe assertion functions for runtime validation.
 *
 * @module assert/assertions
 */

/**
 * Assert a condition is truthy, throwing if false
 *
 * This function acts as a type guard, narrowing the type after the assertion.
 * Uses `function` keyword because TypeScript requires it for `asserts` return type.
 *
 * @param condition - Condition to check
 * @param message - Error message if condition is false
 * @throws Error if condition is falsy
 *
 * @example
 * ```typescript
 * const value: string | undefined = getValue();
 * assert(value !== undefined, 'Value must be defined');
 * // value is now typed as string
 * console.log(value.toUpperCase());
 * ```
 */
export function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

/**
 * Assert value is not null or undefined
 *
 * Narrows the type by removing null and undefined.
 *
 * @param value - Value to check
 * @param name - Name of the value for error message
 * @returns The value if not null/undefined
 * @throws Error if value is null or undefined
 *
 * @example
 * ```typescript
 * const element = document.getElementById('my-id');
 * const definedElement = assertDefined(element, 'element');
 * // definedElement is now HTMLElement, not HTMLElement | null
 * ```
 */
export const assertDefined = <T>(value: T | null | undefined, name: string): T => {
  if (value === null || value === undefined) {
    throw new Error(`${name} is required but was ${value}`);
  }
  return value;
};

/**
 * Assert value is not null
 *
 * Only removes null from the type (keeps undefined if present).
 *
 * @param value - Value to check
 * @param name - Name of the value for error message
 * @returns The value if not null
 * @throws Error if value is null
 */
export const assertNotNull = <T>(value: T | null, name: string): T => {
  if (value === null) {
    throw new Error(`${name} must not be null`);
  }
  return value;
};

/**
 * Assert value is of a specific type using a type guard
 *
 * @param value - Value to check
 * @param guard - Type guard function
 * @param typeName - Name of the expected type for error message
 * @returns The value if type guard passes
 * @throws Error if type guard fails
 *
 * @example
 * ```typescript
 * const value: unknown = getData();
 * const str = assertType(value, isString, 'string');
 * // str is now typed as string
 * ```
 */
export const assertType = <T>(
  value: unknown,
  guard: (v: unknown) => v is T,
  typeName: string,
): T => {
  if (!guard(value)) {
    throw new Error(`Expected ${typeName} but got ${typeof value}`);
  }
  return value;
};

/**
 * Assert that a value is never reached (exhaustive check)
 *
 * Useful for exhaustive switch statements.
 *
 * @param value - Value that should never exist
 * @param message - Optional error message
 * @throws Error always
 *
 * @example
 * ```typescript
 * type Status = 'pending' | 'complete' | 'failed';
 *
 * function handleStatus(status: Status) {
 *   switch (status) {
 *     case 'pending': return 'Waiting...';
 *     case 'complete': return 'Done!';
 *     case 'failed': return 'Error';
 *     default:
 *       assertNever(status); // Compile error if a case is missing
 *   }
 * }
 * ```
 */
export const assertNever = (value: never, message?: string): never => {
  throw new Error(message ?? `Unexpected value: ${JSON.stringify(value)}`);
};

/**
 * Assert that an array is not empty
 *
 * @param array - Array to check
 * @param name - Name of the array for error message
 * @returns The array if not empty
 * @throws Error if array is empty
 */
export const assertNonEmpty = <T>(array: T[], name: string): T[] => {
  if (array.length === 0) {
    throw new Error(`${name} must not be empty`);
  }
  return array;
};

/**
 * Assert that a value is within a numeric range
 *
 * @param value - Value to check
 * @param min - Minimum value (inclusive)
 * @param max - Maximum value (inclusive)
 * @param name - Name of the value for error message
 * @returns The value if within range
 * @throws Error if value is outside range
 */
export const assertInRange = (value: number, min: number, max: number, name: string): number => {
  if (value < min || value > max) {
    throw new Error(`${name} must be between ${min} and ${max}, got ${value}`);
  }
  return value;
};
