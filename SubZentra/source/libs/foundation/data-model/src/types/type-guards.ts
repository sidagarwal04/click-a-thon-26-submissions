/**
 * Type guards for safe type narrowing
 *
 * Provides type guards for Arrow.js types, Maps, entity IDs, and safe value conversions.
 * These guards enable safe handling of dynamic data from DuckDB queries.
 *
 * @module types/type-guards
 */

import type { WithId, WithRequiredId } from './utility';

// =============================================================================
// Arrow.js Type Guards
// =============================================================================

/**
 * Check if a value is an Arrow Vector-like object
 *
 * Arrow Vectors have specific methods like get(), toArray(), and length property.
 * This guard allows safe access to vector data without importing Apache Arrow directly.
 *
 * @param value - Value to check
 * @returns True if the value appears to be an Arrow Vector
 *
 * @example
 * ```typescript
 * if (isArrowVector(column)) {
 *   const firstValue = column.get(0);
 * }
 * ```
 */
export function isArrowVector(value: unknown): value is {
  get: (index: number) => unknown;
  toArray: () => unknown[];
  readonly length: number;
  readonly type: unknown;
} {
  return (
    value !== null &&
    typeof value === 'object' &&
    'get' in value &&
    typeof value.get === 'function' &&
    'toArray' in value &&
    typeof value.toArray === 'function' &&
    'length' in value &&
    typeof value.length === 'number'
  );
}

/**
 * Check if a value is an Arrow Table-like object
 *
 * Arrow Tables have schema, numRows, and getChild methods.
 *
 * @param value - Value to check
 * @returns True if the value appears to be an Arrow Table
 *
 * @example
 * ```typescript
 * if (isArrowTable(result)) {
 *   const column = result.getChild('user_id');
 * }
 * ```
 */
export function isArrowTable(value: unknown): value is {
  readonly schema: { fields: ReadonlyArray<{ name: string; type: unknown }> };
  readonly numRows: number;
  getChild: (name: string) => unknown;
  toArray: () => unknown[];
} {
  return (
    value !== null &&
    typeof value === 'object' &&
    'schema' in value &&
    typeof value.schema === 'object' &&
    value.schema !== null &&
    'fields' in value.schema &&
    'numRows' in value &&
    typeof value.numRows === 'number' &&
    'getChild' in value &&
    typeof value.getChild === 'function'
  );
}

/**
 * Check if a value is an Arrow Field-like object
 *
 * @param value - Value to check
 * @returns True if the value appears to be an Arrow Field
 */
export function isArrowField(value: unknown): value is {
  readonly name: string;
  readonly type: { typeId: number; toString: () => string };
  readonly nullable: boolean;
} {
  return (
    value !== null &&
    typeof value === 'object' &&
    'name' in value &&
    typeof value.name === 'string' &&
    'type' in value &&
    typeof value.type === 'object' &&
    value.type !== null
  );
}

// =============================================================================
// Generic Type Guards
// =============================================================================

/**
 * Check if a value is a Map
 *
 * @param value - Value to check
 * @returns True if value is a Map
 *
 * @example
 * ```typescript
 * if (isMap(value)) {
 *   value.forEach((v, k) => console.log(k, v));
 * }
 * ```
 */
export function isMap<K = unknown, V = unknown>(value: unknown): value is Map<K, V> {
  return value instanceof Map;
}

/**
 * Check if a value is a Set
 *
 * @param value - Value to check
 * @returns True if value is a Set
 */
export function isSet<T = unknown>(value: unknown): value is Set<T> {
  return value instanceof Set;
}

/**
 * Check if a value is a plain object (not null, not array, not class instance)
 *
 * @param value - Value to check
 * @returns True if value is a plain object
 */
export function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === null || proto === Object.prototype;
}

/**
 * Check if a value is a non-null object
 *
 * @param value - Value to check
 * @returns True if value is a non-null object
 */
export function isObject(value: unknown): value is object {
  return value !== null && typeof value === 'object';
}

/**
 * Check if a value is a non-empty string
 *
 * @param value - Value to check
 * @returns True if value is a non-empty string
 */
export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

// =============================================================================
// Safe Value Conversions
// =============================================================================

/**
 * Safely convert a value to a number
 *
 * Handles Arrow Int/Float types, BigInt, strings, and regular numbers.
 * Returns null for values that cannot be converted.
 *
 * @param value - Value to convert
 * @returns Number or null if conversion failed
 *
 * @example
 * ```typescript
 * const num = toNumber(arrowIntValue);
 * if (num !== null) {
 *   console.log('Value:', num);
 * }
 * ```
 */
export function toNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;

  // Handle BigInt (common in Arrow Int64)
  if (typeof value === 'bigint') {
    const num = Number(value);
    if (!Number.isFinite(num)) return null;
    return num;
  }

  // Handle regular numbers
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return null;
    return value;
  }

  // Handle strings
  if (typeof value === 'string') {
    const num = Number(value);
    if (!Number.isFinite(num)) return null;
    return num;
  }

  // Handle objects with valueOf (Arrow numeric types)
  if (typeof value === 'object' && value !== null && 'valueOf' in value) {
    const primitive = (value as { valueOf: () => unknown }).valueOf();
    if (typeof primitive === 'number') {
      if (!Number.isFinite(primitive)) return null;
      return primitive;
    }
    if (typeof primitive === 'bigint') {
      const num = Number(primitive);
      if (!Number.isFinite(num)) return null;
      return num;
    }
  }

  return null;
}

/**
 * Safely convert a value to a string
 *
 * @param value - Value to convert
 * @returns String or null if conversion failed
 */
export function toString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'bigint') return value.toString();
  return null;
}

/**
 * Safely convert a value to a boolean
 *
 * @param value - Value to convert
 * @returns Boolean or null if conversion failed
 */
export function toBoolean(value: unknown): boolean | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string') {
    const lower = value.toLowerCase();
    if (lower === 'true' || lower === '1') return true;
    if (lower === 'false' || lower === '0') return false;
  }
  return null;
}

/**
 * Safely convert a value to an ISO date string
 *
 * Handles Date objects, timestamps (numbers), and date strings.
 *
 * @param value - Value to convert
 * @returns ISO date string or null if conversion failed
 *
 * @example
 * ```typescript
 * const dateStr = toDateIsoString(arrowTimestamp);
 * if (dateStr) {
 *   console.log('Date:', dateStr);
 * }
 * ```
 */
export function toDateIsoString(value: unknown): string | null {
  if (value === null || value === undefined) return null;

  // Already a Date
  if (value instanceof Date) {
    if (isNaN(value.getTime())) return null;
    return value.toISOString();
  }

  // Timestamp as number (milliseconds)
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return null;
    const date = new Date(value);
    if (isNaN(date.getTime())) return null;
    return date.toISOString();
  }

  // Timestamp as BigInt (milliseconds)
  if (typeof value === 'bigint') {
    const date = new Date(Number(value));
    if (isNaN(date.getTime())) return null;
    return date.toISOString();
  }

  // ISO string
  if (typeof value === 'string') {
    const date = new Date(value);
    if (isNaN(date.getTime())) return null;
    return date.toISOString();
  }

  return null;
}

/**
 * Safely convert a value to a Date object
 *
 * @param value - Value to convert
 * @returns Date or null if conversion failed
 */
export function toDate(value: unknown): Date | null {
  if (value === null || value === undefined) return null;

  if (value instanceof Date) {
    return isNaN(value.getTime()) ? null : value;
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    const date = new Date(value);
    return isNaN(date.getTime()) ? null : date;
  }

  if (typeof value === 'bigint') {
    const date = new Date(Number(value));
    return isNaN(date.getTime()) ? null : date;
  }

  if (typeof value === 'string') {
    const date = new Date(value);
    return isNaN(date.getTime()) ? null : date;
  }

  return null;
}

// =============================================================================
// Arrow Value Conversion
// =============================================================================

/**
 * Arrow type IDs (based on Apache Arrow specification)
 */
export const ARROW_TYPE_ID = {
  NONE: 0,
  NULL: 1,
  INT: 2,
  FLOAT: 3,
  BINARY: 4,
  UTF8: 5,
  BOOL: 6,
  DECIMAL: 7,
  DATE: 8,
  TIME: 9,
  TIMESTAMP: 10,
  INTERVAL: 11,
  LIST: 12,
  STRUCT: 13,
  UNION: 14,
  FIXED_SIZE_BINARY: 15,
  FIXED_SIZE_LIST: 16,
  MAP: 17,
  DURATION: 18,
  LARGE_BINARY: 19,
  LARGE_UTF8: 20,
  LARGE_LIST: 21,
} as const;

export type ArrowTypeId = (typeof ARROW_TYPE_ID)[keyof typeof ARROW_TYPE_ID];

/**
 * Safely convert an Arrow value based on field type
 *
 * This function handles the conversion of Arrow column values to JavaScript primitives,
 * taking into account the Arrow field type for proper handling.
 *
 * @param fieldType - The Arrow field type (or type ID)
 * @param value - The value to convert
 * @returns Converted JavaScript value
 *
 * @example
 * ```typescript
 * const jsValue = convertArrowValueSafe(field.type, rawValue);
 * ```
 */
export function convertArrowValueSafe(fieldType: unknown, value: unknown): unknown {
  if (value === null || value === undefined) return null;

  // Get type ID if available
  let typeId: number | undefined;
  if (typeof fieldType === 'object' && fieldType !== null && 'typeId' in fieldType) {
    typeId = (fieldType as { typeId: number }).typeId;
  } else if (typeof fieldType === 'number') {
    typeId = fieldType;
  }

  // Convert based on type
  switch (typeId) {
    case ARROW_TYPE_ID.INT:
    case ARROW_TYPE_ID.FLOAT:
    case ARROW_TYPE_ID.DECIMAL:
      return toNumber(value) ?? value;

    case ARROW_TYPE_ID.UTF8:
    case ARROW_TYPE_ID.LARGE_UTF8:
      return toString(value) ?? value;

    case ARROW_TYPE_ID.BOOL:
      return toBoolean(value) ?? value;

    case ARROW_TYPE_ID.TIMESTAMP:
    case ARROW_TYPE_ID.DATE:
      return toDateIsoString(value) ?? value;

    case ARROW_TYPE_ID.LIST:
    case ARROW_TYPE_ID.LARGE_LIST:
    case ARROW_TYPE_ID.FIXED_SIZE_LIST:
      if (Array.isArray(value)) return value;
      if (isArrowVector(value)) return value.toArray();
      return value;

    case ARROW_TYPE_ID.STRUCT:
    case ARROW_TYPE_ID.MAP:
      // Keep as-is, let caller handle nested structures
      return value;

    default:
      // For unknown types, try basic conversions
      if (typeof value === 'bigint') return Number(value);
      return value;
  }
}

/**
 * Convert an entire Arrow row to a plain JavaScript object
 *
 * @param schema - Arrow table schema
 * @param row - Row object with column names as keys
 * @returns Plain JavaScript object with converted values
 */
export function convertArrowRow(
  schema: { fields: ReadonlyArray<{ name: string; type: unknown }> },
  row: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const field of schema.fields) {
    const value = row[field.name];
    result[field.name] = convertArrowValueSafe(field.type, value);
  }

  return result;
}

// =============================================================================
// Entity ID Type Guards
// =============================================================================

/**
 * Type guard to check if an object has an id property
 *
 * @param obj - Value to check
 * @returns True if object has a string `id` property
 *
 * @example
 * ```typescript
 * if (hasId(entity)) {
 *   console.log(entity.id); // Type-safe access
 * }
 * ```
 */
export const hasId = (obj: unknown): obj is { id: string } => {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    typeof (obj as { id: unknown }).id === 'string'
  );
};

/**
 * Type guard to check if an object has a valid ID.
 */
export const hasAnyId = (obj: unknown): obj is WithRequiredId => hasId(obj);

/**
 * Get the ID from an object.
 */
export const getEntityId = (obj: unknown): string | undefined => (hasId(obj) ? obj.id : undefined);

/**
 * Check if an entity's ID matches a given entityId.
 */
export const matchesEntityId = (item: WithId | WithRequiredId, entityId: string): boolean =>
  item.id === entityId;
