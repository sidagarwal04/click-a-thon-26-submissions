/**
 * Order Types
 *
 * Order specifications for sorting query results.
 *
 * @module types/order
 */

import { extractColumnName, extractTableName } from '../utils/member-ref';

// =============================================================================
// ORDER DIRECTIONS
// =============================================================================

/**
 * Sort direction constants.
 */
export const ORDER_DIRECTIONS = {
  ASC: 'asc',
  DESC: 'desc',
} as const;

export type OrderDirection = (typeof ORDER_DIRECTIONS)[keyof typeof ORDER_DIRECTIONS];

/**
 * Null handling options for ordering.
 */
export const NULLS_HANDLING = {
  FIRST: 'first',
  LAST: 'last',
} as const;

export type NullsHandling = (typeof NULLS_HANDLING)[keyof typeof NULLS_HANDLING];

// =============================================================================
// ORDER BY SPECIFICATION
// =============================================================================

/**
 * Order by specification for sorting results.
 *
 * @example
 * // Ascending order
 * { member: 'users.name', direction: 'asc' }
 *
 * @example
 * // Descending with nulls first
 * { member: 'orders.amount', direction: 'desc', nulls: 'first' }
 */
export interface OrderBySpec {
  /**
   * Member reference to sort by: 'table.column'.
   */
  readonly member: string;

  /**
   * Sort direction.
   * Default: 'asc'
   */
  readonly direction: OrderDirection;

  /**
   * Where to place NULL values.
   * Default: 'last' for ASC, 'first' for DESC (SQL standard)
   */
  readonly nulls?: NullsHandling;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid order direction.
 */
export const isOrderDirection = (value: unknown): value is OrderDirection => {
  return (
    typeof value === 'string' && Object.values(ORDER_DIRECTIONS).includes(value as OrderDirection)
  );
};

/**
 * Check if value is a valid order by specification.
 */
export const isOrderBySpec = (value: unknown): value is OrderBySpec => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  // Required: member must be a string
  if (typeof obj['member'] !== 'string') {
    return false;
  }

  // Required: direction must be valid
  if (!isOrderDirection(obj['direction'])) {
    return false;
  }

  return true;
};

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Extract table name from an order by spec.
 */
export const extractTableFromOrderBy = (orderBy: OrderBySpec): string => {
  return extractTableName(orderBy.member) ?? orderBy.member;
};

/**
 * Extract column name from an order by spec.
 */
export const extractColumnFromOrderBy = (orderBy: OrderBySpec): string => {
  return extractColumnName(orderBy.member) ?? orderBy.member;
};

/**
 * Create an order by specification.
 *
 * @example
 * createOrderBy('users.name') // { member: 'users.name', direction: 'asc' }
 * createOrderBy('users.name', 'desc') // { member: 'users.name', direction: 'desc' }
 */
export const createOrderBy = (
  member: string,
  direction: OrderDirection = 'asc',
  nulls?: NullsHandling,
): OrderBySpec => {
  const spec: OrderBySpec = { member, direction };
  if (nulls) {
    return { ...spec, nulls };
  }
  return spec;
};

/**
 * Create ascending order.
 */
export const asc = (member: string, nulls?: NullsHandling): OrderBySpec =>
  createOrderBy(member, 'asc', nulls);

/**
 * Create descending order.
 */
export const desc = (member: string, nulls?: NullsHandling): OrderBySpec =>
  createOrderBy(member, 'desc', nulls);
