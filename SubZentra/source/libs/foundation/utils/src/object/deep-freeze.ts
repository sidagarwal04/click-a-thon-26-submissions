/**
 * Object immutability utilities
 *
 * @module object/deep-freeze
 */

/**
 * Deep freeze an object to make it completely immutable
 *
 * Recursively freezes all nested objects and arrays.
 * Does not modify the original object, but returns a frozen reference.
 *
 * @param obj - Object to freeze
 * @returns Frozen object (same reference)
 *
 * @example
 * ```typescript
 * const config = deepFreeze({
 *   server: {
 *     host: 'localhost',
 *     port: 3000,
 *   },
 *   features: ['auth', 'logging'],
 * });
 *
 * // These will throw in strict mode or fail silently:
 * config.server.port = 8080; // Error!
 * config.features.push('metrics'); // Error!
 * ```
 */
export const deepFreeze = <T extends object>(obj: T): Readonly<T> => {
  // Get all property names (including non-enumerable)
  const propNames = Object.getOwnPropertyNames(obj);

  // Freeze nested objects/arrays first
  for (const name of propNames) {
    const value = (obj as Record<string, unknown>)[name];

    if (value && typeof value === 'object' && !Object.isFrozen(value)) {
      deepFreeze(value as object);
    }
  }

  return Object.freeze(obj);
};

/**
 * Check if an object is deeply frozen
 *
 * @param obj - Object to check
 * @returns True if object and all nested objects are frozen
 */
export const isDeeplyFrozen = (obj: unknown): boolean => {
  if (typeof obj !== 'object' || obj === null) {
    return true;
  }

  if (!Object.isFrozen(obj)) {
    return false;
  }

  return Object.getOwnPropertyNames(obj).every((name) =>
    isDeeplyFrozen((obj as Record<string, unknown>)[name]),
  );
};
