/**
 * Aggregation Types
 *
 * Defines aggregation functions for measures in queries.
 *
 * @module types/aggregation
 */

// =============================================================================
// AGGREGATION FUNCTIONS
// =============================================================================

/**
 * Supported aggregation functions.
 *
 * - `sum`: Sum of values
 * - `count`: Count of rows
 * - `avg`: Average of values
 * - `min`: Minimum value
 * - `max`: Maximum value
 * - `countDistinct`: Count of distinct values
 * - `sumDistinct`: Sum of distinct values
 * - `avgDistinct`: Average of distinct values
 */
export const AGGREGATIONS = {
  SUM: 'sum',
  COUNT: 'count',
  AVG: 'avg',
  MIN: 'min',
  MAX: 'max',
  COUNT_DISTINCT: 'countDistinct',
  SUM_DISTINCT: 'sumDistinct',
  AVG_DISTINCT: 'avgDistinct',
} as const;

/**
 * Type derived from AGGREGATIONS const object.
 */
export type Aggregation = (typeof AGGREGATIONS)[keyof typeof AGGREGATIONS];

/**
 * Aggregations that count rows (don't require numeric column).
 */
export const COUNT_AGGREGATIONS = {
  COUNT: AGGREGATIONS.COUNT,
  COUNT_DISTINCT: AGGREGATIONS.COUNT_DISTINCT,
} as const;

export type CountAggregation = (typeof COUNT_AGGREGATIONS)[keyof typeof COUNT_AGGREGATIONS];

/**
 * Aggregations that require numeric columns.
 */
export const NUMERIC_AGGREGATIONS = {
  SUM: AGGREGATIONS.SUM,
  AVG: AGGREGATIONS.AVG,
  MIN: AGGREGATIONS.MIN,
  MAX: AGGREGATIONS.MAX,
  SUM_DISTINCT: AGGREGATIONS.SUM_DISTINCT,
  AVG_DISTINCT: AGGREGATIONS.AVG_DISTINCT,
} as const;

export type NumericAggregation = (typeof NUMERIC_AGGREGATIONS)[keyof typeof NUMERIC_AGGREGATIONS];

/**
 * Aggregations that use DISTINCT modifier.
 */
export const DISTINCT_AGGREGATIONS = {
  COUNT_DISTINCT: AGGREGATIONS.COUNT_DISTINCT,
  SUM_DISTINCT: AGGREGATIONS.SUM_DISTINCT,
  AVG_DISTINCT: AGGREGATIONS.AVG_DISTINCT,
} as const;

export type DistinctAggregation =
  (typeof DISTINCT_AGGREGATIONS)[keyof typeof DISTINCT_AGGREGATIONS];

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid aggregation function.
 */
export const isAggregation = (value: unknown): value is Aggregation => {
  return typeof value === 'string' && Object.values(AGGREGATIONS).includes(value as Aggregation);
};

/**
 * Check if aggregation is a count aggregation.
 */
export const isCountAggregation = (value: unknown): value is CountAggregation => {
  return (
    typeof value === 'string' &&
    Object.values(COUNT_AGGREGATIONS).includes(value as CountAggregation)
  );
};

/**
 * Check if aggregation requires a numeric column.
 */
export const isNumericAggregation = (value: unknown): value is NumericAggregation => {
  return (
    typeof value === 'string' &&
    Object.values(NUMERIC_AGGREGATIONS).includes(value as NumericAggregation)
  );
};

/**
 * Check if aggregation uses DISTINCT modifier.
 */
export const isDistinctAggregation = (value: unknown): value is DistinctAggregation => {
  return (
    typeof value === 'string' &&
    Object.values(DISTINCT_AGGREGATIONS).includes(value as DistinctAggregation)
  );
};

// =============================================================================
// SQL GENERATION HELPERS
// =============================================================================

/**
 * Get SQL function name for an aggregation.
 *
 * @param aggregation - The aggregation function
 * @returns SQL function name (e.g., 'SUM', 'COUNT')
 */
export const getAggregationSqlFunction = (aggregation: Aggregation): string => {
  switch (aggregation) {
    case AGGREGATIONS.SUM:
    case AGGREGATIONS.SUM_DISTINCT:
      return 'SUM';
    case AGGREGATIONS.COUNT:
    case AGGREGATIONS.COUNT_DISTINCT:
      return 'COUNT';
    case AGGREGATIONS.AVG:
    case AGGREGATIONS.AVG_DISTINCT:
      return 'AVG';
    case AGGREGATIONS.MIN:
      return 'MIN';
    case AGGREGATIONS.MAX:
      return 'MAX';
    default:
      throw new Error(`Unknown aggregation: ${aggregation as string}`);
  }
};
