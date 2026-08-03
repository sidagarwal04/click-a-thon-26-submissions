/**
 * Apache Arrow to JavaScript Type Converter
 *
 * Converts Arrow table data to proper JavaScript types.
 * Handles BigInt, Date, Timestamp, Decimal, List, Map, Struct, etc.
 *
 * @module duckdb/arrow-converter
 */

import type { Field, StructRowProxy, Table, Vector } from 'apache-arrow';
import { Type } from 'apache-arrow';

/**
 * Convert a single Arrow value to its JavaScript equivalent
 *
 * @param field - Arrow field schema containing type information
 * @param value - Raw value from Arrow
 * @returns Properly typed JavaScript value
 */
export const convertArrowValue = (field: Field, value: unknown): unknown => {
  // Handle null/undefined
  if (value === null || value === undefined) {
    return null;
  }

  switch (field.typeId) {
    // Null type
    case Type.Null:
      return null;

    // Date types - convert to ISO string
    case Type.Date:
    case Type.DateDay:
    case Type.DateMillisecond:
      return value instanceof Date ? value.toISOString() : new Date(value as number).toISOString();

    // Timestamp types - convert to ISO string
    case Type.Timestamp:
    case Type.TimestampSecond:
    case Type.TimestampMillisecond:
    case Type.TimestampMicrosecond:
    case Type.TimestampNanosecond:
      return value instanceof Date ? value.toISOString() : new Date(value as number).toISOString();

    // Time types - keep as number (milliseconds)
    case Type.Time:
    case Type.TimeSecond:
    case Type.TimeMillisecond:
    case Type.TimeMicrosecond:
    case Type.TimeNanosecond:
      return Number(value);

    // Float types - return as-is
    case Type.Float:
    case Type.Float16:
    case Type.Float32:
    case Type.Float64:
      return value;

    // Integer types - handle BigInt conversion
    case Type.Int:
    case Type.Int8:
    case Type.Int16:
    case Type.Int32:
      return typeof value === 'bigint' ? Number(value) : value;

    // 64-bit integers - convert BigInt to number (may lose precision for very large values)
    case Type.Int64:
    case Type.Uint64:
      if (typeof value === 'bigint') {
        // Check if value is within safe integer range
        if (value >= BigInt(Number.MIN_SAFE_INTEGER) && value <= BigInt(Number.MAX_SAFE_INTEGER)) {
          return Number(value);
        }
        // For very large numbers, return as string to preserve precision
        return value.toString();
      }
      return typeof value === 'object' && value !== null
        ? parseInt((value as object).toString(), 10)
        : value;

    // Unsigned integers
    case Type.Uint8:
    case Type.Uint16:
    case Type.Uint32:
      return typeof value === 'bigint' ? Number(value) : value;

    // Decimal - convert to float
    case Type.Decimal:
      return typeof value === 'object' && value !== null
        ? parseFloat((value as object).toString())
        : value;

    // Boolean
    case Type.Bool:
      return Boolean(value);

    // String types
    case Type.Utf8:
    case Type.LargeUtf8:
      return String(value);

    // Binary types - convert to Uint8Array or base64
    case Type.Binary:
    case Type.LargeBinary:
    case Type.FixedSizeBinary:
      if (value instanceof Uint8Array) {
        return value;
      }
      return value;

    // List/Array types - recursively convert elements
    case Type.List:
    case Type.FixedSizeList: {
      const childField = field.type.children?.[0];
      if (!childField) {
        return [];
      }

      const vector = value as Vector;
      if (!vector || typeof vector.toArray !== 'function') {
        return Array.isArray(value) ? value : [];
      }

      return vector.toArray().map((item: unknown) => convertArrowValue(childField, item));
    }

    // Map type
    case Type.Map: {
      const result: Record<string, unknown> = {};
      if (value && typeof value === 'object') {
        const mapValue = value as Map<unknown, unknown>;
        if (mapValue instanceof Map) {
          for (const [k, v] of mapValue) {
            result[String(k)] = v;
          }
        }
      }
      return result;
    }

    // Struct type - recursively convert fields
    case Type.Struct: {
      if (!value || typeof value !== 'object') {
        return null;
      }

      const structFields = field.type.children;
      if (!structFields) {
        return value;
      }

      const result: Record<string, unknown> = {};
      const structValue = value as Record<string, unknown>;

      for (const childField of structFields) {
        result[childField.name] = convertArrowValue(childField, structValue[childField.name]);
      }

      return result;
    }

    // Duration
    case Type.Duration:
    case Type.DurationSecond:
    case Type.DurationMillisecond:
    case Type.DurationMicrosecond:
    case Type.DurationNanosecond:
      return typeof value === 'bigint' ? Number(value) : value;

    // Interval
    case Type.Interval:
    case Type.IntervalDayTime:
    case Type.IntervalYearMonth:
      return value;

    // Union types
    case Type.DenseUnion:
    case Type.SparseUnion:
      return value;

    // Dictionary (categorical)
    case Type.Dictionary:
      return value;

    // Default - return as-is
    default:
      return value;
  }
};

/**
 * Convert an Arrow table row to a JavaScript object
 *
 * @param row - Arrow StructRowProxy
 * @param fields - Schema fields
 * @returns Plain JavaScript object
 */
export const convertArrowRow = <T extends Record<string, unknown>>(
  row: StructRowProxy,
  fields: readonly Field[],
): T => {
  const result: Record<string, unknown> = {};

  for (const field of fields) {
    const rawValue = row[field.name];
    result[field.name] = convertArrowValue(field, rawValue);
  }

  return result as T;
};

/**
 * Convert an entire Arrow table to an array of JavaScript objects
 *
 * @param table - Apache Arrow Table
 * @returns Array of plain JavaScript objects with proper types
 */
export const convertArrowTableToJSON = <T extends Record<string, unknown>>(table: Table): T[] => {
  const fields = table.schema.fields;

  return table.toArray().map((row: StructRowProxy) => convertArrowRow<T>(row, fields));
};

/**
 * Get column metadata from Arrow schema
 *
 * @param table - Apache Arrow Table
 * @returns Object mapping column names to their type information
 */
export const getColumnMetadata = (
  table: Table,
): Record<string, { type: string; typeId: Type; nullable: boolean }> => {
  const metadata: Record<string, { type: string; typeId: Type; nullable: boolean }> = {};

  for (const field of table.schema.fields) {
    metadata[field.name] = {
      type: field.type.toString(),
      typeId: field.typeId,
      nullable: field.nullable,
    };
  }

  return metadata;
};

// =============================================================================
// Query Result Conversion
// =============================================================================

/**
 * Result of converting an Arrow table to a query result
 */
export interface ArrowQueryResult<T = Record<string, unknown>> {
  /** Converted rows as JavaScript objects */
  readonly rows: T[];
  /** Column names */
  readonly columns: string[];
  /** Column types as strings */
  readonly types: string[];
  /** Query execution time in milliseconds */
  readonly executionTimeMs: number;
}

/**
 * Convert an Arrow table to a QueryResult format
 *
 * This is a convenience function that combines table conversion with
 * metadata extraction for use in DuckDB query results.
 *
 * @param arrowTable - Apache Arrow Table from DuckDB query
 * @param executionTimeMs - Execution time in milliseconds
 * @returns Complete query result with rows, columns, types, and timing
 *
 * @example
 * ```typescript
 * const startTime = performance.now();
 * const result = await connection.query(sql);
 * const executionTimeMs = performance.now() - startTime;
 *
 * return convertArrowToQueryResult<User>(result, executionTimeMs);
 * ```
 */
export const convertArrowToQueryResult = <T = Record<string, unknown>>(
  arrowTable: Table,
  executionTimeMs: number,
): ArrowQueryResult<T> => {
  const rows = convertArrowTableToJSON<T & Record<string, unknown>>(arrowTable);
  const columns = arrowTable.schema.fields.map((f) => f.name);
  const types = arrowTable.schema.fields.map((f) => f.type.toString());

  return {
    rows,
    columns,
    types,
    executionTimeMs,
  };
};
