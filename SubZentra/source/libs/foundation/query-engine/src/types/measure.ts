/**
 * Measure Types
 *
 * Object-based measure specification with aggregation support.
 * Presence of measures triggers the DuckDB execution path.
 *
 * @module types/measure
 */

import { extractColumnName, extractTableName } from '../utils/member-ref';
import { AGGREGATIONS, type Aggregation } from './aggregation';
import type { FilterCondition } from './filter';

// =============================================================================
// MEASURE FORMAT TYPES
// =============================================================================

/**
 * Format types for displaying measures
 */
export const MEASURE_FORMAT_TYPES = {
  /** Plain number */
  NUMBER: 'number',
  /** Currency value */
  CURRENCY: 'currency',
  /** Percentage value */
  PERCENTAGE: 'percentage',
  /** Byte size (KB, MB, etc.) */
  BYTES: 'bytes',
  /** Time duration */
  DURATION: 'duration',
  /** Custom format template */
  CUSTOM: 'custom',
} as const;

/**
 * Measure format type derived from MEASURE_FORMAT_TYPES
 */
export type MeasureFormatType = (typeof MEASURE_FORMAT_TYPES)[keyof typeof MEASURE_FORMAT_TYPES];

// =============================================================================
// MEASURE SPECIFICATION
// =============================================================================

/**
 * Object-based measure specification with aggregation.
 *
 * Measures define computed values using aggregation functions.
 * The table is inferred from the `member` property.
 * The presence of measures in a query triggers the DuckDB execution path.
 *
 * @example
 * // Sum of amounts
 * { member: 'orders.amount', aggregation: 'sum' }
 *
 * @example
 * // Sum with alias
 * { member: 'orders.amount', aggregation: 'sum', alias: 'total_revenue' }
 *
 * @example
 * // Count distinct with filter
 * {
 *   member: 'orders.id',
 *   aggregation: 'countDistinct',
 *   alias: 'unique_orders',
 *   filter: { member: 'orders.status', operator: 'equals', values: ['completed'] }
 * }
 */
export interface MeasureSpec {
  /**
   * Member reference in format 'table.column'.
   * The table name is extracted from this reference.
   *
   * @example 'orders.amount'
   * @example 'users.id'
   */
  readonly member: string;

  /**
   * Aggregation function to apply.
   *
   * @example 'sum' | 'count' | 'avg' | 'min' | 'max' | 'countDistinct'
   */
  readonly aggregation: Aggregation;

  /**
   * Optional alias for the result column.
   * If not provided, a default alias is generated.
   *
   * @example 'total_revenue'
   */
  readonly alias?: string;

  /**
   * Use DISTINCT modifier for aggregation.
   * Note: Some aggregations like 'countDistinct' already include DISTINCT.
   */
  readonly distinct?: boolean;

  /**
   * Filter to apply specifically to this measure.
   * Creates a filtered aggregation (CASE WHEN ... THEN ... END pattern).
   *
   * @example
   * // Count only completed orders
   * { member: 'orders.status', operator: 'equals', values: ['completed'] }
   */
  readonly filter?: FilterCondition;

  /**
   * Format specification for display.
   *
   * @example 'currency' | 'percentage' | 'number'
   */
  readonly format?: MeasureFormatType;

  /**
   * Number of decimal places for formatting.
   * Default: 2 for currency/percentage, 0 for number
   */
  readonly decimals?: number;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid MeasureSpec.
 */
export const isMeasureSpec = (value: unknown): value is MeasureSpec => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  // Required: member must be a string in 'table.column' format, or '*' for COUNT(*)
  if (typeof obj['member'] !== 'string') {
    return false;
  }
  if (obj['member'] !== '*' && !obj['member'].includes('.')) {
    return false;
  }

  // Required: aggregation must be a string
  if (typeof obj['aggregation'] !== 'string') {
    return false;
  }

  // Optional: alias must be a string if present
  if (obj['alias'] !== undefined && typeof obj['alias'] !== 'string') {
    return false;
  }

  // Optional: distinct must be a boolean if present
  if (obj['distinct'] !== undefined && typeof obj['distinct'] !== 'boolean') {
    return false;
  }

  return true;
};

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Extract table name from a measure spec.
 *
 * @param measure - The measure specification
 * @returns Table name extracted from the member reference
 *
 * @example
 * extractTableFromMeasure({ member: 'orders.amount', aggregation: 'sum' }) // 'orders'
 */
export const extractTableFromMeasure = (measure: MeasureSpec): string => {
  return extractTableName(measure.member) ?? measure.member;
};

/**
 * Extract column name from a measure spec.
 *
 * @param measure - The measure specification
 * @returns Column name extracted from the member reference
 *
 * @example
 * extractColumnFromMeasure({ member: 'orders.amount', aggregation: 'sum' }) // 'amount'
 */
export const extractColumnFromMeasure = (measure: MeasureSpec): string => {
  return extractColumnName(measure.member) ?? measure.member;
};

/**
 * Get the result alias for a measure.
 * Uses the alias if provided, otherwise generates one from the aggregation and column.
 *
 * @param measure - The measure specification
 * @returns The alias to use in the result
 *
 * @example
 * getMeasureAlias({ member: 'orders.amount', aggregation: 'sum' }) // 'sum_amount'
 * getMeasureAlias({ member: 'orders.amount', aggregation: 'sum', alias: 'total' }) // 'total'
 */
export const getMeasureAlias = (measure: MeasureSpec): string => {
  if (measure.alias) {
    return measure.alias;
  }
  const column = extractColumnFromMeasure(measure);
  return `${measure.aggregation}_${column}`;
};

/**
 * Check if measure uses DISTINCT modifier.
 * Returns true if explicit `distinct: true` or aggregation includes DISTINCT.
 *
 * @param measure - The measure specification
 * @returns Whether DISTINCT should be used
 */
export const measureUsesDistinct = (measure: MeasureSpec): boolean => {
  if (measure.distinct) {
    return true;
  }
  return (
    measure.aggregation === AGGREGATIONS.COUNT_DISTINCT ||
    measure.aggregation === AGGREGATIONS.SUM_DISTINCT ||
    measure.aggregation === AGGREGATIONS.AVG_DISTINCT
  );
};

/**
 * Create a measure spec with required fields.
 *
 * @param member - Member reference in 'table.column' format
 * @param aggregation - Aggregation function
 * @param alias - Optional alias for the result
 * @returns MeasureSpec object
 *
 * @example
 * createMeasure('orders.amount', 'sum') // { member: 'orders.amount', aggregation: 'sum' }
 */
export const createMeasure = (
  member: string,
  aggregation: Aggregation,
  alias?: string,
): MeasureSpec => {
  const spec: MeasureSpec = { member, aggregation };
  if (alias) {
    return { ...spec, alias };
  }
  return spec;
};

/**
 * Create a SUM measure.
 *
 * @param member - Member reference in 'table.column' format
 * @param alias  - Optional alias for the result column
 * @returns MeasureSpec with aggregation 'sum'
 */
export const sumMeasure = (member: string, alias?: string): MeasureSpec =>
  createMeasure(member, AGGREGATIONS.SUM, alias);

/**
 * Create a COUNT measure.
 *
 * @param member - Member reference in 'table.column' format (or '*' for COUNT(*))
 * @param alias  - Optional alias for the result column
 * @returns MeasureSpec with aggregation 'count'
 */
export const countMeasure = (member: string, alias?: string): MeasureSpec =>
  createMeasure(member, AGGREGATIONS.COUNT, alias);

/**
 * Create a COUNT DISTINCT measure.
 *
 * @param member - Member reference in 'table.column' format
 * @param alias  - Optional alias for the result column
 * @returns MeasureSpec with aggregation 'countDistinct'
 */
export const countDistinctMeasure = (member: string, alias?: string): MeasureSpec =>
  createMeasure(member, AGGREGATIONS.COUNT_DISTINCT, alias);

/**
 * Create an AVG measure.
 *
 * @param member - Member reference in 'table.column' format
 * @param alias  - Optional alias for the result column
 * @returns MeasureSpec with aggregation 'avg'
 */
export const avgMeasure = (member: string, alias?: string): MeasureSpec =>
  createMeasure(member, AGGREGATIONS.AVG, alias);

/**
 * Create a MIN measure.
 *
 * @param member - Member reference in 'table.column' format
 * @param alias  - Optional alias for the result column
 * @returns MeasureSpec with aggregation 'min'
 */
export const minMeasure = (member: string, alias?: string): MeasureSpec =>
  createMeasure(member, AGGREGATIONS.MIN, alias);

/**
 * Create a MAX measure.
 *
 * @param member - Member reference in 'table.column' format
 * @param alias  - Optional alias for the result column
 * @returns MeasureSpec with aggregation 'max'
 */
export const maxMeasure = (member: string, alias?: string): MeasureSpec =>
  createMeasure(member, AGGREGATIONS.MAX, alias);
