/**
 * Hook Types
 *
 * Type definitions for useDLQueryEngine and useDLMutateQueryEngine hooks.
 * Uses discriminated unions for type-safe result handling.
 *
 * @module hooks/types
 */

import type { QueryKey } from '@tanstack/react-query';

import {
  isMutationOperation as isCoreMutationOperation,
  WRITE_OPERATIONS,
} from '@open-zentra/foundation-data-model';

import { QUERY_ENGINE_PATHS } from '../internal/constants';
import { QUERY_DATA_SOURCES, type Query, type DataSource as QueryDataSource } from '../types/query';

// =============================================================================
// EXECUTION PATH & DATA SOURCE
// =============================================================================

/**
 * Execution path literal union
 */
export const EXECUTION_PATHS = {
  ANALYTICS: QUERY_ENGINE_PATHS.ANALYTICS,
  TRANSACTIONAL: QUERY_ENGINE_PATHS.TRANSACTIONAL,
} as const;

export type HookExecutionPath = (typeof EXECUTION_PATHS)[keyof typeof EXECUTION_PATHS];

export type ExecutionPath = HookExecutionPath;

/**
 * Data source literal union
 */
export const DATA_SOURCES = {
  ...QUERY_DATA_SOURCES,
} as const;

export type HookDataSource = QueryDataSource;

export type DataSource = HookDataSource;

export const ANALYTICS_DATA_SOURCES = {
  DUCKDB: DATA_SOURCES.DUCKDB,
  CACHE: DATA_SOURCES.CACHE,
  NONE: DATA_SOURCES.NONE,
} as const;

export type AnalyticsDataSource =
  (typeof ANALYTICS_DATA_SOURCES)[keyof typeof ANALYTICS_DATA_SOURCES];

export const TRANSACTIONAL_DATA_SOURCES = {
  API: DATA_SOURCES.API,
  CACHE: DATA_SOURCES.CACHE,
  NONE: DATA_SOURCES.NONE,
} as const;

export type TransactionalDataSource =
  (typeof TRANSACTIONAL_DATA_SOURCES)[keyof typeof TRANSACTIONAL_DATA_SOURCES];

// =============================================================================
// DOWNLOAD PROGRESS
// =============================================================================

/**
 * Download progress information (immutable)
 */
export interface DownloadProgress {
  readonly isDownloading: boolean;
  readonly progress: number; // 0-100
  readonly filesTotal: number;
  readonly filesCompleted: number;
  readonly currentFile: string | null;
}

/**
 * Initial download state (const for reference stability)
 */
export const INITIAL_DOWNLOAD_STATE: DownloadProgress = Object.freeze({
  isDownloading: false,
  progress: 0,
  filesTotal: 0,
  filesCompleted: 0,
  currentFile: null,
});

// =============================================================================
// QUERY HOOK OPTIONS
// =============================================================================

/**
 * Options for useDLQueryEngine
 */
export interface UseDLQueryEngineOptions<TQuery extends Query, TData = unknown> {
  /**
   * The query to execute.
   * Tables are inferred from dimensions, measures, filters, joins.
   */
  readonly query: TQuery;

  /**
   * Whether the query is enabled (default: true).
   */
  readonly enabled?: boolean;

  /**
   * Custom stale time override (ms).
   */
  readonly staleTime?: number;

  /**
   * Custom GC time override (ms).
   */
  readonly gcTime?: number;

  /**
   * Transform function for result data.
   */
  readonly select?: (data: unknown) => TData;

  /**
   * Force a specific execution path (bypasses decision engine).
   */
  readonly forcePath?: ExecutionPath;

  /**
   * Prefer analytics even for simple queries.
   */
  readonly preferAnalytics?: boolean;

  /**
   * Callback when file download progress changes (analytics only).
   */
  readonly onDownloadProgress?: (progress: DownloadProgress) => void;
}

// =============================================================================
// QUERY HOOK RESULT (Discriminated Union)
// =============================================================================

/**
 * Base result fields shared across all paths
 */
interface BaseQueryResult<TData> {
  readonly data: TData | undefined;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly isSuccess: boolean;
  readonly isError: boolean;
  readonly error: Error | null;
  readonly isOffline: boolean;
  readonly isStale: boolean;
  readonly lastUpdatedAt: number | null;
  readonly tables: ReadonlyArray<string>;
  readonly primaryTable: string | null;
  readonly refetch: () => Promise<void>;
  readonly invalidate: () => Promise<void>;
}

/**
 * Analytics result (discriminated)
 */
interface AnalyticsResult<TData> extends BaseQueryResult<TData> {
  readonly executionPath: typeof EXECUTION_PATHS.ANALYTICS;
  readonly dataSource: AnalyticsDataSource;
  readonly sql: string | null;
  readonly executionTimeMs: number | null;
  readonly isDownloadingFiles: boolean;
  readonly downloadProgress: number;
  readonly filesToDownload: number;
  readonly filesDownloaded: number;
}

/**
 * Transactional result (discriminated)
 */
interface TransactionalResult<TData> extends BaseQueryResult<TData> {
  readonly executionPath: typeof EXECUTION_PATHS.TRANSACTIONAL;
  readonly dataSource: TransactionalDataSource;
  readonly sql: null;
  readonly executionTimeMs: null;
  readonly isDownloadingFiles: false;
  readonly downloadProgress: 0;
  readonly filesToDownload: 0;
  readonly filesDownloaded: 0;
}

/**
 * Pending result (before decision)
 */
interface PendingResult<TData> extends BaseQueryResult<TData> {
  readonly executionPath: null;
  readonly dataSource: typeof DATA_SOURCES.NONE;
  readonly sql: null;
  readonly executionTimeMs: null;
  readonly isDownloadingFiles: false;
  readonly downloadProgress: 0;
  readonly filesToDownload: 0;
  readonly filesDownloaded: 0;
}

/**
 * Union of all query result types
 */
export type UseDLQueryEngineResult<TData> =
  | AnalyticsResult<TData>
  | TransactionalResult<TData>
  | PendingResult<TData>;

// =============================================================================
// MUTATION HOOK TYPES
// =============================================================================

/**
 * Supported mutation operations (const object pattern)
 *
 * @example
 * ```typescript
 * // Use as value
 * const op = MUTATION_OPERATIONS.CREATE;
 *
 * // Use as type
 * const handler = (operation: MutationOperation) => { ... };
 * ```
 */
export const MUTATION_OPERATIONS = {
  ...WRITE_OPERATIONS,
} as const;

/**
 * Mutation operation type derived from MUTATION_OPERATIONS
 */
export type MutationOperation = (typeof MUTATION_OPERATIONS)[keyof typeof MUTATION_OPERATIONS];

export const MUTATION_RESULT_OPERATIONS = {
  ...MUTATION_OPERATIONS,
  SQL: 'sql',
} as const;

export type MutationResultOperation =
  (typeof MUTATION_RESULT_OPERATIONS)[keyof typeof MUTATION_RESULT_OPERATIONS];

/**
 * Type guard for mutation operations
 */
export const isMutationOperation = (value: unknown): value is MutationOperation =>
  isCoreMutationOperation(value);

/**
 * Options for useDLMutateQueryEngine
 */
export interface UseDLMutateQueryEngineOptions<TData = unknown, TVariables = unknown> {
  /**
   * Query defining target table and operation.
   * operation should be 'create', 'update', or 'delete'.
   */
  readonly query: Query;

  /**
   * Generate optimistic data from variables.
   * For create: Return full item shape with provisional ID.
   * For update: Return merged item (receives previous data as second arg).
   */
  readonly onOptimistic?: (variables: TVariables, previousData?: TData) => Partial<TData>;

  /**
   * Extract entity ID from variables (for update/delete).
   */
  readonly getEntityId?: (variables: TVariables) => string;

  /**
   * Query keys to invalidate on success.
   */
  readonly invalidateKeys?: ReadonlyArray<QueryKey>;

  /**
   * Success callback.
   */
  readonly onSuccess?: (data: TData, variables: TVariables) => void | Promise<void>;

  /**
   * Error callback.
   */
  readonly onError?: (error: Error, variables: TVariables) => void | Promise<void>;

  /**
   * Settled callback (called on success or error).
   */
  readonly onSettled?: (
    data: TData | undefined,
    error: Error | null,
    variables: TVariables,
  ) => void | Promise<void>;
}

/**
 * Result from useDLMutateQueryEngine
 */
export interface UseDLMutateQueryEngineResult<TData = unknown, TVariables = unknown> {
  // Mutation functions
  readonly mutate: (variables: TVariables) => void;
  readonly mutateAsync: (variables: TVariables) => Promise<TData>;

  // Mutation state
  readonly data: TData | undefined;
  readonly isPending: boolean;
  readonly isSuccess: boolean;
  readonly isError: boolean;
  readonly isIdle: boolean;
  readonly error: Error | null;

  // Offline status
  readonly isQueued: boolean;
  readonly isOffline: boolean;
  readonly provisionalId: string | null;

  // Execution info
  readonly executionPath: HookExecutionPath;
  readonly operation: MutationResultOperation;
  readonly table: string | null;

  // Actions
  readonly reset: () => void;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if result is analytics path
 */
export const isAnalyticsResult = <TData>(
  result: UseDLQueryEngineResult<TData>,
): result is AnalyticsResult<TData> => result.executionPath === EXECUTION_PATHS.ANALYTICS;

/**
 * Check if result is transactional path
 */
export const isTransactionalResult = <TData>(
  result: UseDLQueryEngineResult<TData>,
): result is TransactionalResult<TData> => result.executionPath === EXECUTION_PATHS.TRANSACTIONAL;

/**
 * Check if result is pending (no decision yet)
 */
export const isPendingResult = <TData>(
  result: UseDLQueryEngineResult<TData>,
): result is PendingResult<TData> => result.executionPath === null;
