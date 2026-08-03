/**
 * Filter Types
 *
 * Comprehensive filter operators and condition types for queries.
 * Supports both simple conditions and complex logical groups.
 *
 * @module types/filter
 */

import { extractColumnName, extractTableName } from '../utils/member-ref';

// =============================================================================
// FILTER OPERATORS
// =============================================================================

/**
 * Equality operators for exact matching.
 */
export const EQUALITY_OPERATORS = {
  EQUALS: 'equals',
  NOT_EQUALS: 'notEquals',
} as const;

export type EqualityOperator = (typeof EQUALITY_OPERATORS)[keyof typeof EQUALITY_OPERATORS];

/**
 * Comparison operators for numeric/date comparisons.
 */
export const COMPARISON_OPERATORS = {
  GT: 'gt',
  GTE: 'gte',
  LT: 'lt',
  LTE: 'lte',
  BETWEEN: 'between',
} as const;

export type ComparisonOperator = (typeof COMPARISON_OPERATORS)[keyof typeof COMPARISON_OPERATORS];

/**
 * String operators for text matching.
 */
export const STRING_OPERATORS = {
  CONTAINS: 'contains',
  NOT_CONTAINS: 'notContains',
  STARTS_WITH: 'startsWith',
  ENDS_WITH: 'endsWith',
  MATCHES: 'matches',
} as const;

export type StringOperator = (typeof STRING_OPERATORS)[keyof typeof STRING_OPERATORS];

/**
 * Set operators for array/list matching.
 */
export const SET_OPERATORS = {
  IN: 'in',
  NOT_IN: 'notIn',
} as const;

export type SetOperator = (typeof SET_OPERATORS)[keyof typeof SET_OPERATORS];

/**
 * Null operators for null checking.
 */
export const NULL_OPERATORS = {
  IS_NULL: 'isNull',
  IS_NOT_NULL: 'isNotNull',
} as const;

export type NullOperator = (typeof NULL_OPERATORS)[keyof typeof NULL_OPERATORS];

/**
 * Array operators for array column operations.
 */
export const ARRAY_OPERATORS = {
  ARRAY_CONTAINS: 'arrayContains',
  ARRAY_CONTAINS_ANY: 'arrayContainsAny',
  ARRAY_CONTAINS_ALL: 'arrayContainsAll',
} as const;

export type ArrayOperator = (typeof ARRAY_OPERATORS)[keyof typeof ARRAY_OPERATORS];

/**
 * All supported filter operators combined.
 */
export const FILTER_OPERATORS = {
  ...EQUALITY_OPERATORS,
  ...COMPARISON_OPERATORS,
  ...STRING_OPERATORS,
  ...SET_OPERATORS,
  ...NULL_OPERATORS,
  ...ARRAY_OPERATORS,
} as const;

export type FilterOperator = (typeof FILTER_OPERATORS)[keyof typeof FILTER_OPERATORS];

/**
 * Operators that don't require values.
 */
export const VALUELESS_FILTER_OPERATORS = {
  IS_NULL: NULL_OPERATORS.IS_NULL,
  IS_NOT_NULL: NULL_OPERATORS.IS_NOT_NULL,
} as const;

/**
 * Operators that require exactly one value.
 */
export const SINGLE_VALUE_FILTER_OPERATORS = {
  EQUALS: EQUALITY_OPERATORS.EQUALS,
  NOT_EQUALS: EQUALITY_OPERATORS.NOT_EQUALS,
  GT: COMPARISON_OPERATORS.GT,
  GTE: COMPARISON_OPERATORS.GTE,
  LT: COMPARISON_OPERATORS.LT,
  LTE: COMPARISON_OPERATORS.LTE,
  CONTAINS: STRING_OPERATORS.CONTAINS,
  NOT_CONTAINS: STRING_OPERATORS.NOT_CONTAINS,
  STARTS_WITH: STRING_OPERATORS.STARTS_WITH,
  ENDS_WITH: STRING_OPERATORS.ENDS_WITH,
  MATCHES: STRING_OPERATORS.MATCHES,
} as const;

/**
 * Operators that require multiple values.
 */
export const MULTI_VALUE_FILTER_OPERATORS = {
  IN: SET_OPERATORS.IN,
  NOT_IN: SET_OPERATORS.NOT_IN,
  BETWEEN: COMPARISON_OPERATORS.BETWEEN,
  ARRAY_CONTAINS_ANY: ARRAY_OPERATORS.ARRAY_CONTAINS_ANY,
  ARRAY_CONTAINS_ALL: ARRAY_OPERATORS.ARRAY_CONTAINS_ALL,
} as const;

// =============================================================================
// FILTER CONDITION
// =============================================================================

/**
 * Value type for filter conditions.
 * Supports primitives, dates, and null.
 */
export type FilterValue = string | number | boolean | Date | null;

/**
 * Primitive filter value types.
 *
 * Alias for `FilterValue` used in builder/preset APIs where the name
 * "primitive" better communicates intent. Both names are part of the
 * public API — prefer `FilterPrimitive` in builder contexts and
 * `FilterValue` in compiler/SQL contexts.
 */
export type FilterPrimitive = FilterValue;

/**
 * A single filter condition.
 *
 * @example
 * // Equality filter
 * { member: 'users.status', operator: 'equals', values: ['active'] }
 *
 * @example
 * // Comparison filter
 * { member: 'orders.amount', operator: 'gte', values: [100] }
 *
 * @example
 * // Between filter
 * { member: 'orders.created_at', operator: 'between', values: ['2024-01-01', '2024-12-31'] }
 *
 * @example
 * // Null check (no values needed)
 * { member: 'users.deleted_at', operator: 'isNull' }
 */
export interface FilterCondition {
  /**
   * Member reference in format 'table.column'.
   * The table name is extracted from this reference.
   */
  readonly member: string;

  /**
   * Filter operator to apply.
   */
  readonly operator: FilterOperator;

  /**
   * Values for the filter condition.
   * Optional for null operators, required for most other operators.
   */
  readonly values?: ReadonlyArray<FilterPrimitive>;

  /**
   * Case sensitivity for string operations.
   * Default: false (case-sensitive)
   */
  readonly caseInsensitive?: boolean;
}

// =============================================================================
// LOGICAL FILTER GROUPS
// =============================================================================

/**
 * Logical AND group of filter conditions.
 * All conditions must be true for the group to match.
 *
 * @example
 * {
 *   and: [
 *     { member: 'users.status', operator: 'equals', values: ['active'] },
 *     { member: 'users.role', operator: 'equals', values: ['admin'] }
 *   ]
 * }
 */
export interface FilterAndGroup {
  readonly and: ReadonlyArray<FilterExpression>;
}

/**
 * Logical OR group of filter conditions.
 * At least one condition must be true for the group to match.
 *
 * @example
 * {
 *   or: [
 *     { member: 'users.status', operator: 'equals', values: ['active'] },
 *     { member: 'users.status', operator: 'equals', values: ['pending'] }
 *   ]
 * }
 */
export interface FilterOrGroup {
  readonly or: ReadonlyArray<FilterExpression>;
}

/**
 * Logical filter group (AND or OR).
 */
export type FilterGroup = FilterAndGroup | FilterOrGroup;

/**
 * A filter expression is either a simple condition or a logical group.
 * This allows for building complex nested filter trees.
 *
 * @example
 * // Complex nested filter
 * {
 *   and: [
 *     { member: 'users.status', operator: 'equals', values: ['active'] },
 *     {
 *       or: [
 *         { member: 'users.role', operator: 'equals', values: ['admin'] },
 *         { member: 'users.role', operator: 'equals', values: ['superuser'] }
 *       ]
 *     }
 *   ]
 * }
 */
export type FilterExpression = FilterCondition | FilterGroup;

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid filter operator.
 */
export const isFilterOperator = (value: unknown): value is FilterOperator => {
  return (
    typeof value === 'string' && Object.values(FILTER_OPERATORS).includes(value as FilterOperator)
  );
};

/**
 * Check if value is a filter condition (not a group).
 */
export const isFilterCondition = (value: unknown): value is FilterCondition => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  // Must have member and operator
  if (typeof obj['member'] !== 'string' || typeof obj['operator'] !== 'string') {
    return false;
  }

  // Must not have 'and' or 'or' properties (those are groups)
  if ('and' in obj || 'or' in obj) {
    return false;
  }

  return true;
};

/**
 * Check if value is an AND filter group.
 */
export const isFilterAndGroup = (value: unknown): value is FilterAndGroup => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;
  return 'and' in obj && Array.isArray(obj['and']);
};

/**
 * Check if value is an OR filter group.
 */
export const isFilterOrGroup = (value: unknown): value is FilterOrGroup => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;
  return 'or' in obj && Array.isArray(obj['or']);
};

/**
 * Check if value is a filter group (AND or OR).
 */
export const isFilterGroup = (value: unknown): value is FilterGroup => {
  return isFilterAndGroup(value) || isFilterOrGroup(value);
};

/**
 * Check if value is a valid filter expression (condition or group).
 */
export const isFilterExpression = (value: unknown): value is FilterExpression => {
  return isFilterCondition(value) || isFilterGroup(value);
};

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Check if operator requires values.
 */
export const operatorRequiresValues = (operator: FilterOperator): boolean => {
  return !Object.values(VALUELESS_FILTER_OPERATORS).includes(
    operator as (typeof VALUELESS_FILTER_OPERATORS)[keyof typeof VALUELESS_FILTER_OPERATORS],
  );
};

/**
 * Check if operator accepts multiple values.
 */
export const operatorAcceptsMultipleValues = (operator: FilterOperator): boolean => {
  return Object.values(MULTI_VALUE_FILTER_OPERATORS).includes(
    operator as (typeof MULTI_VALUE_FILTER_OPERATORS)[keyof typeof MULTI_VALUE_FILTER_OPERATORS],
  );
};

/**
 * Extract table name from a filter condition.
 */
export const extractTableFromFilter = (filter: FilterCondition): string => {
  return extractTableName(filter.member) ?? filter.member;
};

/**
 * Extract column name from a filter condition.
 */
export const extractColumnFromFilter = (filter: FilterCondition): string => {
  return extractColumnName(filter.member) ?? filter.member;
};

/**
 * Create a filter condition.
 *
 * @example
 * createFilterCondition('users.status', 'equals', ['active'])
 */
export const createFilterCondition = (
  member: string,
  operator: FilterOperator,
  values?: ReadonlyArray<FilterPrimitive>,
): FilterCondition => {
  if (values !== undefined) {
    return { member, operator, values };
  }
  return { member, operator };
};

/**
 * Create an AND filter group.
 */
export const andFilter = (...conditions: ReadonlyArray<FilterExpression>): FilterAndGroup => ({
  and: conditions,
});

/**
 * Create an OR filter group.
 */
export const orFilter = (...conditions: ReadonlyArray<FilterExpression>): FilterOrGroup => ({
  or: conditions,
});

/**
 * Shorthand filter creators for common operations.
 */
export const eq = (member: string, value: FilterPrimitive): FilterCondition =>
  createFilterCondition(member, 'equals', [value]);

export const neq = (member: string, value: FilterPrimitive): FilterCondition =>
  createFilterCondition(member, 'notEquals', [value]);

export const gt = (member: string, value: number | Date): FilterCondition =>
  createFilterCondition(member, 'gt', [value]);

export const gte = (member: string, value: number | Date): FilterCondition =>
  createFilterCondition(member, 'gte', [value]);

export const lt = (member: string, value: number | Date): FilterCondition =>
  createFilterCondition(member, 'lt', [value]);

export const lte = (member: string, value: number | Date): FilterCondition =>
  createFilterCondition(member, 'lte', [value]);

export const between = (
  member: string,
  low: number | Date | string,
  high: number | Date | string,
): FilterCondition => createFilterCondition(member, 'between', [low, high]);

export const inList = (member: string, values: ReadonlyArray<FilterPrimitive>): FilterCondition =>
  createFilterCondition(member, 'in', values);

export const notInList = (
  member: string,
  values: ReadonlyArray<FilterPrimitive>,
): FilterCondition => createFilterCondition(member, 'notIn', values);

export const contains = (member: string, value: string): FilterCondition =>
  createFilterCondition(member, 'contains', [value]);

export const startsWith = (member: string, value: string): FilterCondition =>
  createFilterCondition(member, 'startsWith', [value]);

export const endsWith = (member: string, value: string): FilterCondition =>
  createFilterCondition(member, 'endsWith', [value]);

export const isNull = (member: string): FilterCondition => createFilterCondition(member, 'isNull');

export const isNotNull = (member: string): FilterCondition =>
  createFilterCondition(member, 'isNotNull');
