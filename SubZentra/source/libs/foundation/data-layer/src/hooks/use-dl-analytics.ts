/**
 * useDLAnalytics - DuckDB analytics query hook
 *
 * TanStack Query hook for DuckDB analytics queries.
 * Does NOT use offline persistence (analytics queries are ephemeral).
 *
 * For parameterized queries, use DuckDB's native $1, $2 positional syntax
 * and pass params array in options.
 *
 * @module hooks/use-dl-analytics
 */

import { useCallback } from 'react';

import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from '@tanstack/react-query';

import type { DuckDBResult, DuckDBRow } from '@open-zentra/foundation-bridge';

import { ANALYTICS_QUERY_RETRY_MAX, QUERY_RETRY_DELAY_BASE_MS } from '../core/constants';
import { useDataLayerInternals } from '../provider/data-layer-internals-context';
import { getAnalyticsRouterOrThrow } from '../utils/analytics-runtime';

// =============================================================================
// Types
// =============================================================================

/**
 * Options for useDLAnalytics hook
 */
export interface UseDLAnalyticsOptions<TData extends DuckDBRow = DuckDBRow> {
  /** SQL query to execute */
  readonly sql: string;
  /** Positional query parameters ($1, $2, etc.) */
  readonly params?: readonly unknown[];
  /** Custom query key */
  readonly queryKey: QueryKey;
  /** Whether the query is enabled */
  readonly enabled?: boolean;
  /** Stale time in milliseconds */
  readonly staleTime?: number;
  /** Garbage collection time in milliseconds */
  readonly gcTime?: number;
  /** Transform the result */
  readonly select?: (result: DuckDBResult<TData>) => DuckDBResult<TData>;
}

/**
 * Result from useDLAnalytics hook
 */
export interface DLAnalyticsResult<TData extends DuckDBRow = DuckDBRow>
  extends Omit<UseQueryResult<DuckDBResult<TData>, Error>, 'data'> {
  /** The query result */
  readonly data: DuckDBResult<TData> | undefined;
  /** Rows from the result (convenience accessor) */
  readonly rows: TData[];
  /** Execution time in milliseconds */
  readonly executionTimeMs: number | null;
  /** Whether DuckDB is available */
  readonly isAvailable: boolean;
}

/**
 * Analytics query hook for DuckDB
 *
 * @example
 * ```tsx
 * // Simple query
 * const { rows, isLoading } = useDLAnalytics({
 *   sql: `SELECT page, COUNT(*) as views FROM events GROUP BY page`,
 *   queryKey: ['analytics', 'pageViews'],
 * });
 *
 * // With positional parameters ($1, $2)
 * const { rows } = useDLAnalytics({
 *   sql: `SELECT * FROM events WHERE type = $1 AND timestamp > $2`,
 *   params: ['page_view', '2024-01-01'],
 *   queryKey: ['analytics', 'filtered', type, date],
 * });
 * ```
 */
export const useDLAnalytics = <TData extends DuckDBRow = DuckDBRow>(
  options: UseDLAnalyticsOptions<TData>,
): DLAnalyticsResult<TData> => {
  const { duckdbRouter, cacheConfig, analyticsEnabled, initializeAnalytics } =
    useDataLayerInternals();

  const {
    sql,
    params,
    queryKey,
    enabled = true,
    staleTime = cacheConfig.analyticsStaleTime,
    gcTime = cacheConfig.analyticsGcTime,
    select,
  } = options;

  const isDuckDBAvailable = analyticsEnabled;

  // Query function - lazily initialize analytics runtime on first use.
  const queryFn = useCallback(async (): Promise<DuckDBResult<TData>> => {
    const router = await getAnalyticsRouterOrThrow({
      duckdbRouter,
      initializeAnalytics,
    });
    return router.query<TData>(sql, params ? { params } : undefined);
  }, [duckdbRouter, initializeAnalytics, sql, params]);

  // Execute query
  const queryOptions: UseQueryOptions<DuckDBResult<TData>, Error, DuckDBResult<TData>, QueryKey> = {
    queryKey,
    queryFn,
    enabled: enabled && isDuckDBAvailable,
    staleTime,
    gcTime,
    networkMode: 'always',
    retry: ANALYTICS_QUERY_RETRY_MAX,
    retryDelay: QUERY_RETRY_DELAY_BASE_MS,
  };

  if (select !== undefined) {
    queryOptions.select = select;
  }

  const queryResult = useQuery(queryOptions);

  return {
    ...queryResult,
    data: queryResult.data,
    executionTimeMs: queryResult.data?.executionTimeMs ?? null,
    isAvailable: isDuckDBAvailable,
    rows: queryResult.data?.rows ?? [],
  };
};

/**
 * Create analytics query key
 */
export const createAnalyticsQueryKey = (
  category: string,
  name: string,
  ...args: unknown[]
): QueryKey => ['analytics', category, name, ...args];
