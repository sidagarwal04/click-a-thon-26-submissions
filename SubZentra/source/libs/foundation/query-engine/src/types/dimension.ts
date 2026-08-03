/**
 * Dimension Types
 *
 * Object-based dimension specification for type-safe query building.
 * Tables are inferred from member references (e.g., 'users.name' → 'users').
 *
 * @module types/dimension
 */

import { extractColumnName, extractTableName } from '../utils/member-ref';

// =============================================================================
// DIMENSION FORMAT TYPES
// =============================================================================

/**
 * Supported display formats for dimension values.
 */
export const DIMENSION_FORMAT_TYPES = {
  /** Date only (e.g. 2024-01-15) */
  DATE: 'date',
  /** Full date and time */
  DATETIME: 'datetime',
  /** Time only (e.g. 14:30:00) */
  TIME: 'time',
  /** Currency formatted value */
  CURRENCY: 'currency',
  /** Percentage value */
  PERCENT: 'percent',
} as const;

/**
 * Dimension format type derived from DIMENSION_FORMAT_TYPES.
 */
export type DimensionFormatType =
  (typeof DIMENSION_FORMAT_TYPES)[keyof typeof DIMENSION_FORMAT_TYPES];

// =============================================================================
// DIMENSION SPECIFICATION
// =============================================================================

/**
 * Object-based dimension specification.
 *
 * Dimensions define the columns to select and group by in a query.
 * The table is inferred from the `member` property.
 *
 * @example
 * // Simple dimension
 * { member: 'users.name' }
 *
 * @example
 * // Dimension with alias
 * { member: 'users.name', alias: 'user_name' }
 *
 * @example
 * // Time dimension with formatting
 * { member: 'orders.created_at', alias: 'order_date', format: 'date' }
 */
export interface DimensionSpec {
  /**
   * Member reference in format 'table.column'.
   * The table name is extracted from this reference.
   *
   * @example 'users.name'
   * @example 'orders.status'
   */
  readonly member: string;

  /**
   * Optional alias for the result column.
   * If not provided, defaults to the column name.
   *
   * @example 'user_name'
   */
  readonly alias?: string;

  /**
   * Optional format for display purposes.
   * Primarily used for date/time columns.
   *
   * @example 'date' | 'datetime' | 'time' | 'currency' | 'percent'
   */
  readonly format?: DimensionFormatType;

  /**
   * Whether to include NULL values.
   * Default: true
   */
  readonly includeNull?: boolean;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid DimensionSpec.
 */
export const isDimensionSpec = (value: unknown): value is DimensionSpec => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  // Required: member must be a string in 'table.column' format
  if (typeof obj['member'] !== 'string' || !obj['member'].includes('.')) {
    return false;
  }

  // Optional: alias must be a string if present
  if (obj['alias'] !== undefined && typeof obj['alias'] !== 'string') {
    return false;
  }

  // Optional: format must be a valid DimensionFormatType if present
  if (
    obj['format'] !== undefined &&
    (typeof obj['format'] !== 'string' ||
      !Object.values(DIMENSION_FORMAT_TYPES).includes(obj['format'] as DimensionFormatType))
  ) {
    return false;
  }

  // Optional: includeNull must be a boolean if present
  if (obj['includeNull'] !== undefined && typeof obj['includeNull'] !== 'boolean') {
    return false;
  }

  return true;
};

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Extract table name from a dimension spec.
 *
 * @param dimension - The dimension specification
 * @returns Table name extracted from the member reference
 *
 * @example
 * extractTableFromDimension({ member: 'users.name' }) // 'users'
 */
export const extractTableFromDimension = (dimension: DimensionSpec): string => {
  return extractTableName(dimension.member) ?? dimension.member;
};

/**
 * Extract column name from a dimension spec.
 *
 * @param dimension - The dimension specification
 * @returns Column name extracted from the member reference
 *
 * @example
 * extractColumnFromDimension({ member: 'users.name' }) // 'name'
 */
export const extractColumnFromDimension = (dimension: DimensionSpec): string => {
  return extractColumnName(dimension.member) ?? dimension.member;
};

/**
 * Get the result alias for a dimension.
 * Uses the alias if provided, otherwise uses the column name.
 *
 * @param dimension - The dimension specification
 * @returns The alias to use in the result
 *
 * @example
 * getDimensionAlias({ member: 'users.name' }) // 'name'
 * getDimensionAlias({ member: 'users.name', alias: 'user_name' }) // 'user_name'
 */
export const getDimensionAlias = (dimension: DimensionSpec): string => {
  if (dimension.alias) {
    return dimension.alias;
  }
  return extractColumnFromDimension(dimension);
};

/**
 * Create a dimension spec from a member reference.
 *
 * @param member - Member reference in 'table.column' format
 * @param alias - Optional alias for the result
 * @returns DimensionSpec object
 *
 * @example
 * createDimension('users.name') // { member: 'users.name' }
 * createDimension('users.name', 'user_name') // { member: 'users.name', alias: 'user_name' }
 */
export const createDimension = (member: string, alias?: string): DimensionSpec => {
  const spec: DimensionSpec = { member };
  if (alias) {
    return { ...spec, alias };
  }
  return spec;
};
