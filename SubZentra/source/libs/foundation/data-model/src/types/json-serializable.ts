/**
 * JSON-serializable type definitions
 *
 * Core type definitions for JSON-serializable data used throughout
 * the foundation libraries.
 *
 * @module types/json-serializable
 */

// =============================================================================
// Core JSON Types (standardized naming)
// =============================================================================

/**
 * JSON primitive types
 */
export type JsonPrimitive = string | number | boolean | null;

/**
 * JSON object type (recursive)
 */
export type JsonObject = { [key: string]: JsonValue };

/**
 * JSON array type (recursive)
 */
export type JsonArray = JsonValue[];

/**
 * JSON value - any valid JSON type
 *
 * This is the canonical type for JSON-serializable data.
 * Prefer using this over JsonSerializable for new code.
 */
export type JsonValue = JsonPrimitive | JsonObject | JsonArray;

// =============================================================================
// Legacy Types (for backward compatibility)
// =============================================================================

/**
 * JSON-serializable type constraint for data stored in databases and caches.
 *
 * This ensures data can be safely stored in IndexedDB and serialized to JSON.
 * Used for:
 * - Query cache entries
 * - Mutation queue payloads
 * - Sync state values
 * - API request/response data
 *
 * @example
 * ```typescript
 * // Valid JsonSerializable values
 * const str: JsonSerializable = 'hello';
 * const num: JsonSerializable = 42;
 * const bool: JsonSerializable = true;
 * const arr: JsonSerializable = [1, 2, 3];
 * const obj: JsonSerializable = { key: 'value' };
 * const nested: JsonSerializable = { arr: [1, { nested: true }] };
 *
 * // Invalid (not serializable)
 * // const fn: JsonSerializable = () => {}; // Error!
 * // const date: JsonSerializable = new Date(); // Error!
 * // const map: JsonSerializable = new Map(); // Error!
 * ```
 *
 */
export type JsonSerializable = JsonValue;

/**
 * Type guard to check if a value is JSON-serializable
 *
 * Performs a recursive check to validate that the value can be safely
 * serialized to JSON.
 *
 * @param value - Value to check
 * @returns True if value is JSON-serializable
 */
export const isJsonSerializable = (value: unknown): value is JsonSerializable => {
  if (value === null) return true;

  const type = typeof value;

  if (type === 'string' || type === 'number' || type === 'boolean') {
    return true;
  }

  if (Array.isArray(value)) {
    return value.every(isJsonSerializable);
  }

  if (type === 'object') {
    // Check that it's a plain object (not a class instance)
    if (Object.getPrototypeOf(value) !== Object.prototype) {
      return false;
    }

    return Object.values(value as object).every(isJsonSerializable);
  }

  return false;
};

/**
 * Deep clone a JSON-serializable value
 *
 * Uses JSON.parse/stringify for guaranteed deep cloning of serializable values.
 *
 * @param value - Value to clone
 * @returns Deep cloned value
 */
export const cloneJsonSerializable = <T extends JsonSerializable>(value: T): T => {
  return JSON.parse(JSON.stringify(value));
};

/**
 * Error thrown when a value cannot be converted to JsonSerializable
 */
export class JsonSerializationError extends Error {
  constructor(public readonly value: unknown, public readonly reason: string) {
    super(`Value is not JSON-serializable: ${reason}`);
    this.name = 'JsonSerializationError';
  }
}

/**
 * Safely convert a value to JsonSerializable with validation
 *
 * This function validates the value and returns it as JsonSerializable.
 * Unlike using `as JsonSerializable`, this provides runtime validation.
 *
 * @param value - Value to convert
 * @returns The value as JsonSerializable
 * @throws JsonSerializationError if value is not serializable
 *
 * @example
 * ```typescript
 * // Safe conversion with validation
 * const data = toJsonSerializable({ name: 'John', age: 30 });
 *
 * // Throws if value contains non-serializable data
 * try {
 *   toJsonSerializable({ fn: () => {} }); // Throws!
 * } catch (e) {
 *   console.error('Cannot serialize function');
 * }
 * ```
 */
export const toJsonSerializable = <T>(value: T): JsonSerializable => {
  if (isJsonSerializable(value)) {
    return value;
  }

  // Provide helpful error messages for common non-serializable types
  if (typeof value === 'function') {
    throw new JsonSerializationError(value, 'Functions cannot be serialized');
  }

  if (typeof value === 'undefined') {
    throw new JsonSerializationError(value, 'undefined cannot be serialized (use null instead)');
  }

  if (typeof value === 'symbol') {
    throw new JsonSerializationError(value, 'Symbols cannot be serialized');
  }

  if (typeof value === 'bigint') {
    throw new JsonSerializationError(
      value,
      'BigInt cannot be serialized (convert to string first)',
    );
  }

  if (value instanceof Date) {
    throw new JsonSerializationError(
      value,
      'Date objects cannot be serialized (use .toISOString())',
    );
  }

  if (value instanceof Map) {
    throw new JsonSerializationError(value, 'Map cannot be serialized (convert to Object first)');
  }

  if (value instanceof Set) {
    throw new JsonSerializationError(value, 'Set cannot be serialized (convert to Array first)');
  }

  throw new JsonSerializationError(value, 'Value contains non-serializable data');
};

/**
 * Try to convert a value to JsonSerializable, returning null if it fails
 *
 * This is a safe version that doesn't throw, useful when you want to
 * attempt serialization without error handling.
 *
 * @param value - Value to convert
 * @returns The value as JsonSerializable, or null if not serializable
 *
 * @example
 * ```typescript
 * const data = tryToJsonSerializable({ name: 'John' }); // { name: 'John' }
 * const invalid = tryToJsonSerializable(() => {}); // null
 * ```
 */
export const tryToJsonSerializable = <T>(value: T): JsonSerializable | null => {
  if (isJsonSerializable(value)) {
    return value;
  }
  return null;
};

/**
 * Assert that a value is JsonSerializable (type narrowing)
 *
 * This function asserts the type at compile time and validates at runtime.
 * Unlike `toJsonSerializable`, this doesn't return a value - it only throws
 * if validation fails.
 *
 * @param value - Value to assert
 * @throws JsonSerializationError if value is not serializable
 *
 * @example
 * ```typescript
 * function processData(data: unknown) {
 *   assertJsonSerializable(data);
 *   // data is now typed as JsonSerializable
 *   await database.save(data);
 * }
 * ```
 */
export function assertJsonSerializable(value: unknown): asserts value is JsonSerializable {
  if (!isJsonSerializable(value)) {
    if (typeof value === 'function') {
      throw new JsonSerializationError(value, 'Functions cannot be serialized');
    }
    throw new JsonSerializationError(value, 'Value contains non-serializable data');
  }
}
