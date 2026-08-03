/**
 * Join Types
 *
 * Join specifications for multi-table queries.
 * Presence of joins triggers the DuckDB execution path.
 * Tables are inferred from left/right member references.
 *
 * @module types/join
 */

import { extractColumnName, extractTableName } from '../utils/member-ref';

// =============================================================================
// JOIN TYPES
// =============================================================================

/**
 * Supported SQL join types.
 *
 * - `inner`: Only matching rows from both tables
 * - `left`: All rows from left table, matching from right
 * - `right`: All rows from right table, matching from left
 * - `full`: All rows from both tables
 * - `cross`: Cartesian product (every combination)
 */
export const JOIN_TYPES = {
  INNER: 'inner',
  LEFT: 'left',
  RIGHT: 'right',
  FULL: 'full',
  CROSS: 'cross',
} as const;

export type JoinType = (typeof JOIN_TYPES)[keyof typeof JOIN_TYPES];

// =============================================================================
// JOIN SPECIFICATION
// =============================================================================

/**
 * Join specification defining how two tables are related.
 *
 * Tables are inferred from the left and right member references.
 * The presence of joins in a query triggers the DuckDB execution path.
 *
 * @example
 * // Inner join on user_id
 * {
 *   left: 'orders.user_id',
 *   right: 'users.id',
 *   type: 'inner'
 * }
 *
 * @example
 * // Left join with alias
 * {
 *   left: 'orders.user_id',
 *   right: 'users.id',
 *   type: 'left',
 *   alias: 'order_user'
 * }
 *
 * @example
 * // Multiple conditions (AND)
 * {
 *   left: 'orders.user_id',
 *   right: 'users.id',
 *   type: 'inner',
 *   additionalConditions: [
 *     { left: 'orders.company_id', right: 'users.company_id' }
 *   ]
 * }
 */
export interface JoinSpec {
  /**
   * Left side member reference: 'table.column'.
   * The table name is extracted from this reference.
   *
   * @example 'orders.user_id'
   */
  readonly left: string;

  /**
   * Right side member reference: 'table.column'.
   * The table name is extracted from this reference.
   *
   * @example 'users.id'
   */
  readonly right: string;

  /**
   * Type of join to perform.
   * Default: 'inner'
   */
  readonly type: JoinType;

  /**
   * Optional alias for the joined result.
   * Useful when joining the same table multiple times.
   */
  readonly alias?: string;

  /**
   * Additional join conditions (AND with the main condition).
   * Useful for composite keys or complex join logic.
   */
  readonly additionalConditions?: ReadonlyArray<{
    readonly left: string;
    readonly right: string;
  }>;

  /**
   * Whether to use a USING clause instead of ON.
   * Only applicable when left and right columns have the same name.
   */
  readonly usingClause?: boolean;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid join type.
 */
export const isJoinType = (value: unknown): value is JoinType => {
  return typeof value === 'string' && Object.values(JOIN_TYPES).includes(value as JoinType);
};

/**
 * Check if value is a valid join specification.
 */
export const isJoinSpec = (value: unknown): value is JoinSpec => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  // Required: left must be a string in 'table.column' format
  if (typeof obj['left'] !== 'string' || !obj['left'].includes('.')) {
    return false;
  }

  // Required: right must be a string in 'table.column' format
  if (typeof obj['right'] !== 'string' || !obj['right'].includes('.')) {
    return false;
  }

  // Required: type must be a valid join type
  if (!isJoinType(obj['type'])) {
    return false;
  }

  return true;
};

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Extract left table name from a join spec.
 *
 * @param join - The join specification
 * @returns Table name from the left side
 *
 * @example
 * extractLeftTable({ left: 'orders.user_id', right: 'users.id', type: 'inner' }) // 'orders'
 */
export const extractLeftTable = (join: JoinSpec): string => {
  return extractTableName(join.left) ?? join.left;
};

/**
 * Extract right table name from a join spec.
 *
 * @param join - The join specification
 * @returns Table name from the right side
 *
 * @example
 * extractRightTable({ left: 'orders.user_id', right: 'users.id', type: 'inner' }) // 'users'
 */
export const extractRightTable = (join: JoinSpec): string => {
  return extractTableName(join.right) ?? join.right;
};

/**
 * Extract left column name from a join spec.
 */
export const extractLeftColumn = (join: JoinSpec): string => {
  return extractColumnName(join.left) ?? join.left;
};

/**
 * Extract right column name from a join spec.
 */
export const extractRightColumn = (join: JoinSpec): string => {
  return extractColumnName(join.right) ?? join.right;
};

/**
 * Extract both tables from a join spec.
 *
 * @param join - The join specification
 * @returns Array of [leftTable, rightTable]
 */
export const extractTablesFromJoin = (join: JoinSpec): readonly [string, string] => {
  return [extractLeftTable(join), extractRightTable(join)] as const;
};

/**
 * Get SQL keyword for a join type.
 *
 * @param type - The join type
 * @returns SQL keyword string
 *
 * @example
 * getJoinSqlKeyword('inner') // 'INNER JOIN'
 * getJoinSqlKeyword('left') // 'LEFT OUTER JOIN'
 */
export const getJoinSqlKeyword = (type: JoinType): string => {
  switch (type) {
    case JOIN_TYPES.INNER:
      return 'INNER JOIN';
    case JOIN_TYPES.LEFT:
      return 'LEFT OUTER JOIN';
    case JOIN_TYPES.RIGHT:
      return 'RIGHT OUTER JOIN';
    case JOIN_TYPES.FULL:
      return 'FULL OUTER JOIN';
    case JOIN_TYPES.CROSS:
      return 'CROSS JOIN';
    default:
      throw new Error(`Unknown join type: ${type as string}`);
  }
};

/**
 * Create a join specification.
 *
 * @param left - Left member reference
 * @param right - Right member reference
 * @param type - Join type (default: 'inner')
 * @returns JoinSpec object
 *
 * @example
 * createJoin('orders.user_id', 'users.id')
 * createJoin('orders.user_id', 'users.id', 'left')
 */
export const createJoin = (left: string, right: string, type: JoinType = 'inner'): JoinSpec => ({
  left,
  right,
  type,
});

/**
 * Create an inner join.
 *
 * @param left  - Left member reference (e.g. 'orders.user_id')
 * @param right - Right member reference (e.g. 'users.id')
 * @returns JoinSpec with type 'inner'
 */
export const innerJoin = (left: string, right: string): JoinSpec =>
  createJoin(left, right, JOIN_TYPES.INNER);

/**
 * Create a left outer join.
 *
 * @param left  - Left member reference
 * @param right - Right member reference
 * @returns JoinSpec with type 'left'
 */
export const leftJoin = (left: string, right: string): JoinSpec =>
  createJoin(left, right, JOIN_TYPES.LEFT);

/**
 * Create a right outer join.
 *
 * @param left  - Left member reference
 * @param right - Right member reference
 * @returns JoinSpec with type 'right'
 */
export const rightJoin = (left: string, right: string): JoinSpec =>
  createJoin(left, right, JOIN_TYPES.RIGHT);

/**
 * Create a full outer join.
 *
 * @param left  - Left member reference
 * @param right - Right member reference
 * @returns JoinSpec with type 'full'
 */
export const fullJoin = (left: string, right: string): JoinSpec =>
  createJoin(left, right, JOIN_TYPES.FULL);
