/**
 * Query Types
 *
 * The main Query interface and related types.
 * Tables are inferred from query members (dimensions, measures, filters, joins).
 *
 * @module types/query
 */

import type { QueryId } from '@open-zentra/foundation-data-model';
import {
  isMutationOperation,
  isReadOperation,
  OPERATIONS,
  type Operation,
} from '@open-zentra/foundation-data-model';

import type { DimensionSpec } from './dimension';
import type { FilterExpression } from './filter';
import type { JoinSpec } from './join';
import type { MeasureSpec } from './measure';
import type { OrderBySpec } from './order';
import type { TimeDimensionSpec } from './time';

// =============================================================================
// QUERY BACKENDS
// =============================================================================

/**
 * Available query backends
 */
export const QUERY_BACKENDS = {
  /** DuckDB analytical backend for complex queries */
  ANALYTICAL: 'analytical',
  /** HTTP transactional backend for CRUD operations */
  TRANSACTIONAL: 'transactional',
} as const;

/**
 * Query backend type derived from QUERY_BACKENDS
 */
export type QueryBackend = (typeof QUERY_BACKENDS)[keyof typeof QUERY_BACKENDS];

/**
 * Data sources for query execution results.
 */
export const QUERY_DATA_SOURCES = {
  API: 'api',
  DUCKDB: 'duckdb',
  CACHE: 'cache',
  NONE: 'none',
} as const;

/**
 * Data source type derived from QUERY_DATA_SOURCES.
 */
export type DataSource = (typeof QUERY_DATA_SOURCES)[keyof typeof QUERY_DATA_SOURCES];

// =============================================================================
// FRESHNESS REQUIREMENTS
// =============================================================================

/**
 * Data freshness requirements for **per-query** execution.
 *
 * Specifies how fresh the data must be when executing a query.
 * Includes `HISTORICAL` for queries that explicitly accept stale data.
 *
 * @see ANALYTICS_FRESHNESS_LEVELS in `./table` for per-table analytics configuration
 *      (does not include `historical` because table-level config describes capability,
 *      not a per-query staleness tolerance).
 */
export const FRESHNESS_REQUIREMENTS = {
  /** Real-time data required - always fetch from source */
  REALTIME: 'realtime',
  /** Near real-time - cache for very short duration */
  NEAR_REALTIME: 'near-realtime',
  /** Eventually consistent - longer cache duration acceptable */
  EVENTUAL: 'eventual',
  /** Historical data - can use stale cache */
  HISTORICAL: 'historical',
} as const;

/**
 * Freshness requirement type derived from FRESHNESS_REQUIREMENTS
 */
export type FreshnessRequirement =
  (typeof FRESHNESS_REQUIREMENTS)[keyof typeof FRESHNESS_REQUIREMENTS];

// =============================================================================
// QUERY
// =============================================================================

/**
 * Query specification.
 *
 * This is the primary interface for defining queries in the query engine.
 * Tables are NEVER specified explicitly - they are inferred from:
 * - `dimensions` → { member: 'users.name' } → table: 'users'
 * - `measures` → { member: 'orders.amount', aggregation: 'sum' } → table: 'orders'
 * - `filters` → { member: 'products.status', ... } → table: 'products'
 * - `joins` → { left: 'orders.user_id', right: 'users.id' } → tables: 'orders', 'users'
 *
 * The presence of certain properties triggers the DuckDB execution path:
 * - `joins` (any joins require SQL)
 * - `measures` (aggregations require SQL)
 * - Multiple tables inferred (requires joins)
 *
 * @example
 * // Simple list query (API path)
 * {
 *   dimensions: [{ member: 'users.name' }, { member: 'users.email' }],
 *   filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
 * }
 *
 * @example
 * // Aggregation query (DuckDB path)
 * {
 *   dimensions: [{ member: 'orders.status' }],
 *   measures: [{ member: 'orders.amount', aggregation: 'sum', alias: 'total' }],
 * }
 *
 * @example
 * // Join query (DuckDB path)
 * {
 *   dimensions: [{ member: 'users.country' }],
 *   measures: [{ member: 'orders.amount', aggregation: 'sum', alias: 'total' }],
 *   joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],
 * }
 *
 * @example
 * // Get single entity by ID
 * {
 *   operation: 'get',
 *   dimensions: [{ member: 'users.id' }],
 *   entityId: '123',
 * }
 *
 * @example
 * // Create mutation
 * {
 *   operation: 'create',
 *   dimensions: [{ member: 'users.name' }],
 *   data: { name: 'John', email: 'john@example.com' },
 * }
 */
export interface Query {
  /**
   * Optional query identifier for correlation and caching.
   */
  readonly queryId?: QueryId;

  /**
   * Operation type.
   *
   * - 'get': Retrieve single entity by ID
   * - 'list': Retrieve multiple entities (default)
   * - 'create': Create new entity (mutation)
   * - 'update': Update existing entity (mutation)
   * - 'delete': Delete existing entity (mutation)
   *
   * Default: 'list'
   */
  readonly operation?: Operation;

  /**
   * Dimensions define columns to select (and group by for aggregations).
   *
   * Each dimension specifies a member reference in 'table.column' format.
   * The table name is inferred from these references.
   *
   * @example
   * [{ member: 'users.name' }, { member: 'users.email' }]
   */
  readonly dimensions?: ReadonlyArray<DimensionSpec>;

  /**
   * Measures define aggregation operations.
   *
   * The presence of measures triggers the DuckDB execution path.
   * Each measure specifies an aggregation function to apply.
   *
   * @example
   * [{ member: 'orders.amount', aggregation: 'sum', alias: 'total' }]
   */
  readonly measures?: ReadonlyArray<MeasureSpec>;

  /**
   * Filters restrict the result set.
   *
   * Can be simple conditions or complex logical groups (AND/OR).
   *
   * @example
   * [{ member: 'users.status', operator: 'equals', values: ['active'] }]
   */
  readonly filters?: ReadonlyArray<FilterExpression>;

  /**
   * Joins define relationships between tables.
   *
   * The presence of joins triggers the DuckDB execution path.
   * Tables are inferred from left and right member references.
   *
   * @example
   * [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }]
   */
  readonly joins?: ReadonlyArray<JoinSpec>;

  /**
   * Order by specifications for sorting results.
   *
   * @example
   * [{ member: 'orders.created_at', direction: 'desc' }]
   */
  readonly orderBy?: ReadonlyArray<OrderBySpec>;

  /**
   * Time dimensions for date truncation and date range filtering.
   *
   * Each time dimension specifies a date/time column with optional:
   * - `granularity`: Generates DATE_TRUNC in SELECT and GROUP BY
   * - `dateRange`: Generates BETWEEN filter in WHERE clause
   *
   * The presence of timeDimensions triggers the DuckDB execution path.
   *
   * @example
   * // Group orders by month with a date range filter
   * [{ dimension: 'orders.created_at', granularity: 'month', dateRange: 'last_30_days' }]
   */
  readonly timeDimensions?: ReadonlyArray<TimeDimensionSpec>;

  /**
   * Maximum number of rows to return.
   * Applies after filtering and sorting.
   */
  readonly limit?: number;

  /**
   * Number of rows to skip.
   * Applies after filtering and sorting, before limit.
   */
  readonly offset?: number;

  /**
   * Entity ID for GET/UPDATE/DELETE operations.
   *
   * Required for 'get', 'update', and 'delete' operations.
   */
  readonly entityId?: string;

  /**
   * Data payload for CREATE/UPDATE operations.
   *
   * Required for 'create' operations, optional for 'update'.
   */
  readonly data?: Readonly<Record<string, unknown>>;

  /**
   * Whether the query is enabled.
   *
   * If false, the query will not execute.
   * Useful for conditional queries based on user interaction.
   *
   * Default: true
   */
  readonly enabled?: boolean;

  /**
   * Required data freshness.
   */
  readonly freshness?: FreshnessRequirement;

  /**
   * Hint for which backend to use.
   */
  readonly backendHint?: QueryBackend;

  /**
   * Timezone for date/time calculations.
   */
  readonly timezone?: string;

  /**
   * Custom metadata attached to the query.
   * Passed through to results and can be used for tracking/analytics.
   */
  readonly metadata?: Readonly<Record<string, unknown>>;

  /**
   * Whether to skip GROUP BY when supported by backend.
   */
  readonly ungrouped?: boolean;

  /**
   * Whether total row count should be included.
   */
  readonly withTotal?: boolean;

  /**
   * Whether subscription mode is requested.
   */
  readonly subscription?: boolean;
}

// =============================================================================
// QUERY VALIDATION
// =============================================================================

/**
 * Validation result for a query.
 */
export interface QueryValidationResult {
  /** Whether the query is valid */
  readonly isValid: boolean;
  /** List of validation errors (empty if valid) */
  readonly errors: ReadonlyArray<QueryValidationError>;
  /** List of validation warnings (non-blocking issues) */
  readonly warnings: ReadonlyArray<QueryValidationWarning>;
}

/**
 * A single validation error.
 */
export interface QueryValidationError {
  /** Error code for programmatic handling */
  readonly code: string;
  /** Human-readable error message */
  readonly message: string;
  /** Path to the problematic field */
  readonly path?: string;
}

/**
 * A single validation warning.
 */
export interface QueryValidationWarning {
  /** Warning code for programmatic handling */
  readonly code: string;
  /** Human-readable warning message */
  readonly message: string;
  /** Path to the field with the issue */
  readonly path?: string;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid Query.
 */
export const isQuery = (value: unknown): value is Query => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  // Must have at least one query element
  const hasQueryElements =
    obj['dimensions'] !== undefined ||
    obj['measures'] !== undefined ||
    obj['filters'] !== undefined ||
    obj['entityId'] !== undefined;

  return hasQueryElements;
};

/**
 * Check if query requires DuckDB execution.
 *
 * DuckDB is required when:
 * - Query has joins
 * - Query has measures (aggregations)
 * - Query involves multiple tables
 */
export const queryRequiresDuckDB = (query: Query): boolean => {
  // Has joins
  if (query.joins && query.joins.length > 0) {
    return true;
  }

  // Has measures (aggregations)
  if (query.measures && query.measures.length > 0) {
    return true;
  }

  // Has time dimensions (date truncation / range filtering)
  if (query.timeDimensions && query.timeDimensions.length > 0) {
    return true;
  }

  return false;
};

/**
 * Check if query is a mutation (create/update/delete).
 */
export const isMutationQuery = (query: Query): boolean => {
  return query.operation !== undefined && isMutationOperation(query.operation);
};

/**
 * Check if query is a read operation (get/list).
 */
export const isReadQuery = (query: Query): boolean => {
  return query.operation === undefined || isReadOperation(query.operation);
};

/**
 * Check if a value is a valid QueryBackend
 */
export const isQueryBackend = (value: unknown): value is QueryBackend =>
  typeof value === 'string' && Object.values(QUERY_BACKENDS).includes(value as QueryBackend);

/**
 * Check if a value is a valid FreshnessRequirement
 */
export const isFreshnessRequirement = (value: unknown): value is FreshnessRequirement =>
  typeof value === 'string' &&
  Object.values(FRESHNESS_REQUIREMENTS).includes(value as FreshnessRequirement);

// =============================================================================
// QUERY UTILITIES
// =============================================================================

/**
 * Get the effective operation for a query.
 * Returns 'list' if operation is not specified.
 */
export const getQueryOperation = (query: Query): Operation => {
  return query.operation ?? OPERATIONS.LIST;
};

/**
 * Create a minimal list query for a table.
 *
 * @param table - Table name
 * @param columns - Column names to select
 * @returns Query
 *
 * @example
 * createListQuery('users', ['name', 'email'])
 */
export const createListQuery = (table: string, columns: ReadonlyArray<string>): Query => ({
  dimensions: columns.map((col) => ({ member: `${table}.${col}` })),
});

/**
 * Create a get-by-id query.
 *
 * @param table - Table name
 * @param entityId - Entity ID
 * @returns Query
 *
 * @example
 * createGetQuery('users', '123')
 */
export const createGetQuery = (table: string, entityId: string): Query => ({
  operation: OPERATIONS.GET,
  dimensions: [{ member: `${table}.id` }],
  entityId,
});

/**
 * Create a count query for a table.
 *
 * @param table - Table name
 * @param column - Column to count (default: '*' or 'id')
 * @returns Query
 */
export const createCountQuery = (table: string, column = 'id'): Query => ({
  measures: [{ member: `${table}.${column}`, aggregation: 'count', alias: 'count' }],
});
