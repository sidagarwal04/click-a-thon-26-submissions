/**
 * Result Types for Foundation Query Engine
 *
 * Defines types for query results and execution metadata.
 * Uses const objects with derived types pattern.
 *
 * @module types/result
 */

import type { ExecutionId, JsonValue, QueryId } from '@open-zentra/foundation-data-model';

import type { DataSource, QueryBackend } from './query';

// =============================================================================
// EXECUTION STATUS - Const object pattern
// =============================================================================

/**
 * Query execution status values
 */
export const EXECUTION_STATUS = {
  /** Execution is pending */
  PENDING: 'pending',
  /** Execution is running */
  RUNNING: 'running',
  /** Execution completed successfully */
  COMPLETED: 'completed',
  /** Execution failed */
  FAILED: 'failed',
  /** Execution was cancelled */
  CANCELLED: 'cancelled',
} as const;

/**
 * Execution status type derived from EXECUTION_STATUS
 */
export type ExecutionStatus = (typeof EXECUTION_STATUS)[keyof typeof EXECUTION_STATUS];

// =============================================================================
// RESULT STRUCTURES
// =============================================================================

/**
 * Query result row - generic key-value mapping
 */
export type ResultRow = Record<string, JsonValue>;

/**
 * Column metadata in result set
 */
export interface ResultColumn {
  /** Column name */
  readonly name: string;
  /** Column data type */
  readonly type: string;
  /** Original table name (if known) */
  readonly table?: string;
  /** Whether the column is nullable */
  readonly nullable?: boolean;
}

/**
 * Query result with data and metadata
 */
export interface QueryResult<TRow = ResultRow> {
  /** Result rows */
  readonly data: ReadonlyArray<TRow>;
  /** Column metadata */
  readonly columns: ReadonlyArray<ResultColumn>;
  /** Total row count (if requested) */
  readonly total?: number;
  /** Whether more results are available */
  readonly hasMore?: boolean;
  /** Offset for pagination */
  readonly offset?: number;
  /** Limit that was applied */
  readonly limit?: number;
}

/**
 * Execution timing information
 */
export interface ExecutionTiming {
  /** Total execution time in milliseconds */
  readonly totalMs: number;
  /** Time spent on planning */
  readonly planningMs?: number;
  /** Time spent on compilation */
  readonly compilationMs?: number;
  /** Time spent on execution */
  readonly executionMs?: number;
  /** Time spent on result processing */
  readonly processingMs?: number;
}

/**
 * Execution metadata
 */
export interface ExecutionMetadata {
  /** Unique execution identifier */
  readonly executionId: ExecutionId;
  /** Query identifier */
  readonly queryId?: QueryId;
  /** Backend that executed the query */
  readonly backend: QueryBackend;
  /** Data source */
  readonly dataSource: DataSource;
  /** Execution status */
  readonly status: ExecutionStatus;
  /** Timing information */
  readonly timing: ExecutionTiming;
  /** Compiled SQL (if applicable) */
  readonly sql?: string;
  /** Number of rows affected/returned */
  readonly rowCount?: number;
  /** Whether result was from cache */
  readonly fromCache?: boolean;
  /** Cache key used (if applicable) */
  readonly cacheKey?: string;
  /** Execution start timestamp */
  readonly startedAt: number;
  /** Execution end timestamp */
  readonly completedAt?: number;
  /** Error information (if failed) */
  readonly error?: ExecutionError;
}

/**
 * Execution error information
 */
export interface ExecutionError {
  /** Error code */
  readonly code: string;
  /** Error message */
  readonly message: string;
  /** Error details */
  readonly details?: Record<string, unknown>;
  /** SQL state (for SQL errors) */
  readonly sqlState?: string;
  /** Stack trace (in development) */
  readonly stack?: string;
}

/**
 * Complete execution result with data and metadata
 */
export interface ExecutionResult<TRow = ResultRow> {
  /** Query result data */
  readonly result: QueryResult<TRow>;
  /** Execution metadata */
  readonly metadata: ExecutionMetadata;
}

/**
 * Aggregation result with comparison data
 */
export interface AggregationResult<TRow = ResultRow> extends QueryResult<TRow> {
  /** Comparison period data (for period-over-period) */
  readonly comparison?: {
    readonly data: ReadonlyArray<TRow>;
    readonly dateRange: readonly [string, string];
  };
  /** Annotations for the result */
  readonly annotations?: Record<string, unknown>;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if a value is a valid execution status
 */
export const isExecutionStatus = (value: unknown): value is ExecutionStatus =>
  typeof value === 'string' && Object.values(EXECUTION_STATUS).includes(value as ExecutionStatus);

/**
 * Check if an execution completed successfully
 */
export const isSuccessfulExecution = (metadata: ExecutionMetadata): boolean =>
  metadata.status === EXECUTION_STATUS.COMPLETED;

/**
 * Check if an execution failed
 */
export const isFailedExecution = (metadata: ExecutionMetadata): boolean =>
  metadata.status === EXECUTION_STATUS.FAILED;

// =============================================================================
// RESULT HELPERS
// =============================================================================

/**
 * Create an empty query result
 */
export const createEmptyResult = <TRow = ResultRow>(): QueryResult<TRow> => ({
  data: [],
  columns: [],
  total: 0,
  hasMore: false,
});

/**
 * Create execution metadata for a new execution
 */
export const createExecutionMetadata = (
  backend: QueryBackend,
  dataSource: DataSource,
  options?: {
    queryId?: QueryId;
    sql?: string;
  },
): ExecutionMetadata => ({
  executionId: `exec_${Date.now()}_${Math.random().toString(36).slice(2, 9)}` as ExecutionId,
  queryId: options?.queryId,
  backend,
  dataSource,
  status: EXECUTION_STATUS.PENDING,
  timing: { totalMs: 0 },
  sql: options?.sql,
  startedAt: Date.now(),
});

/**
 * Update execution metadata with completion info
 */
export const completeExecution = (
  metadata: ExecutionMetadata,
  result: {
    rowCount?: number;
    fromCache?: boolean;
    error?: ExecutionError;
  },
): ExecutionMetadata => {
  const completedAt = Date.now();
  return {
    ...metadata,
    status: result.error ? EXECUTION_STATUS.FAILED : EXECUTION_STATUS.COMPLETED,
    timing: {
      ...metadata.timing,
      totalMs: completedAt - metadata.startedAt,
    },
    rowCount: result.rowCount,
    fromCache: result.fromCache,
    completedAt,
    error: result.error,
  };
};

/**
 * Transform result rows with a mapping function
 */
export const transformResult = <TIn extends ResultRow, TOut>(
  result: QueryResult<TIn>,
  transform: (row: TIn, index: number) => TOut,
): QueryResult<TOut> => ({
  ...result,
  data: result.data.map(transform),
});

/**
 * Paginate a result
 */
export const paginateResult = <TRow extends ResultRow>(
  result: QueryResult<TRow>,
  offset: number,
  limit: number,
): QueryResult<TRow> => ({
  ...result,
  data: result.data.slice(offset, offset + limit),
  offset,
  limit,
  hasMore: offset + limit < (result.total ?? result.data.length),
});
