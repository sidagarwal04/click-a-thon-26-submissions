/**
 * useDLQueryEngine - Unified Query Hook
 *
 * Main query hook that routes between analytics (DuckDB) and transactional (HTTP API)
 * paths based on query structure. Uses Data Layer hooks for actual execution.
 *
 * Features:
 * - Automatic routing via Decision Engine
 * - SQL compilation for analytics queries
 * - Unified result type with discriminated unions
 * - Uses singleton engine components for better memory efficiency
 * - Background file sync for analytics tables (stale-while-revalidate)
 *
 * NOTE: This hook delegates ALL execution to foundation-data-layer.
 * It does NOT directly access DuckDB or the HTTP transport directly.
 *
 * @module hooks/use-dl-query-engine
 */

import { useCallback, useMemo } from 'react';

import {
  createAnalyticsQueryKey,
  useBackgroundFileSync,
  useDataLayerInternals,
  useDLAnalytics,
  useDLGet,
} from '@open-zentra/foundation-data-layer';
import type { ApiQueryDescriptor } from '@open-zentra/foundation-data-model';
import { OPERATIONS } from '@open-zentra/foundation-data-model';
import { EMPTY_ARRAY, EMPTY_OBJECT, hashPayloadSync } from '@open-zentra/foundation-utils';

import { getSqlCompiler } from '../compiler/sql-compiler';
import { getDecisionEngine } from '../engine/decision-engine';
import { convertFiltersToArgs } from '../engine/filter-converter';
import { getTableExtractor } from '../engine/table-extractor';
import { HOOK_PATH_TO_DECISION_PATH } from '../internal/constants';
import {
  DECISION_PATHS,
  type DecisionContext,
  type DecisionResult,
  type DecisionTableConfig,
} from '../types/decision';
import type { Query } from '../types/query';
import {
  getAnyQueryReference,
  getGetQueryReference,
  getListQueryReference,
} from './internal/data-layer-adapters';
import {
  DATA_SOURCES,
  EXECUTION_PATHS,
  type UseDLQueryEngineOptions,
  type UseDLQueryEngineResult,
} from './types';

// =============================================================================
// HOOK IMPLEMENTATION
// =============================================================================

const selectQueryResultData = <TData>(rawData: unknown, select?: (data: unknown) => TData): TData =>
  select ? select(rawData) : (rawData as TData);

const NOOP_QUERY_DESCRIPTOR: ApiQueryDescriptor<unknown, unknown> = {
  path: '/__query-engine_unreachable__',
};

/**
 * useDLQueryEngine
 *
 * Unified query hook with intelligent routing between analytics (DuckDB)
 * and transactional (HTTP API) paths.
 *
 * Uses singleton engine components for better memory efficiency:
 * - TableExtractor: Shared singleton for extracting tables from queries
 * - SqlCompiler: Shared singleton with LRU cache for SQL compilation
 * - DecisionEngine: Shared singleton for routing decisions
 *
 * Delegates execution to data-layer hooks:
 * - useDLAnalytics: For DuckDB analytics queries
 * - useDLGetList: For transactional API queries
 *
 * @typeParam TQuery - Query type (inferred from query prop)
 * @typeParam TData - Result data type (inferred or specified via select)
 *
 * @example
 * ```tsx
 * // Analytics query (auto-routed to DuckDB)
 * const { data, sql, executionTimeMs } = useDLQueryEngine({
 *   query: {
 *     dimensions: [{ member: 'users.country' }],
 *     measures: [{ member: 'orders.amount', aggregation: 'sum' }],
 *   },
 * });
 *
 * // Transactional query (auto-routed to the API layer)
 * const { data } = useDLQueryEngine({
 *   query: {
 *     dimensions: [{ member: 'users.name' }],
 *     filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
 *   },
 * });
 * ```
 */
export const useDLQueryEngine = <TQuery extends Query, TData = unknown>(
  options: UseDLQueryEngineOptions<TQuery, TData>,
): UseDLQueryEngineResult<TData> => {
  const { query, enabled = true, staleTime, gcTime, select, forcePath, preferAnalytics } = options;

  // ─────────────────────────────────────────────────────────────────────────
  // DATA LAYER CONTEXT
  // ─────────────────────────────────────────────────────────────────────────

  const { isOnline, duckdbRouter, tableRegistry, queryClient, cacheConfig } =
    useDataLayerInternals();

  // ─────────────────────────────────────────────────────────────────────────
  // ENGINE COMPONENTS (Singletons)
  // ─────────────────────────────────────────────────────────────────────────

  // Use singleton engine components for better memory efficiency
  const tableExtractor = getTableExtractor();
  const sqlCompiler = getSqlCompiler();
  const decisionEngine = getDecisionEngine();

  // ─────────────────────────────────────────────────────────────────────────
  // TABLE EXTRACTION
  // ─────────────────────────────────────────────────────────────────────────

  const extraction = useMemo(() => tableExtractor.extractDetailed(query), [tableExtractor, query]);

  const tables = extraction.tables;
  const primaryTable = extraction.primaryTable;

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD TABLE CONFIGS FOR DECISION
  // ─────────────────────────────────────────────────────────────────────────

  const tableConfigs = useMemo(() => {
    const configs = new Map<string, DecisionTableConfig>();
    for (const tableName of tables) {
      const config = tableRegistry.getTable(tableName);
      if (config) {
        configs.set(tableName, {
          api: config.api,
          source: config.api ? 'api' : 'local',
          ...(config.analytics?.freshness !== undefined
            ? { analytics: { freshness: config.analytics.freshness } }
            : {}),
        });
      }
    }
    return configs;
  }, [tables, tableRegistry]);

  // ─────────────────────────────────────────────────────────────────────────
  // ROUTING DECISION
  // ─────────────────────────────────────────────────────────────────────────

  const decision = useMemo((): DecisionResult | null => {
    if (!enabled || tables.length === 0) return null;

    const context: DecisionContext = {
      tables: [...tables],
      operation: query.operation ?? OPERATIONS.LIST,
      tableConfigs,
      isOnline,
      isDuckDBAvailable: duckdbRouter !== null,
    };

    return decisionEngine.decide(query, context, {
      forcePath: forcePath ? HOOK_PATH_TO_DECISION_PATH[forcePath] : undefined,
      preferAnalytics,
      includeFactors: false,
    });
  }, [
    enabled,
    query,
    tables,
    tableConfigs,
    isOnline,
    duckdbRouter,
    decisionEngine,
    forcePath,
    preferAnalytics,
  ]);

  const isAnalyticsPath = decision?.path === DECISION_PATHS.DUCKDB;
  const isTransactionalPath = decision?.path === DECISION_PATHS.API;

  // ─────────────────────────────────────────────────────────────────────────
  // BACKGROUND FILE SYNC (analytics path only)
  // ─────────────────────────────────────────────────────────────────────────

  // Use background file sync for analytics tables
  // This implements stale-while-revalidate: return cached data immediately
  // while downloading newer files in the background
  const backgroundSync = useBackgroundFileSync({
    tables: [...tables],
    enabled: isAnalyticsPath && enabled,
    onProgress: options.onDownloadProgress,
    onComplete: () => {
      // Invalidate analytics queries when new data is downloaded
      void queryClient.invalidateQueries({
        queryKey: ['analytics'],
        refetchType: 'active',
      });
    },
  });

  // Use background sync state for download progress
  const downloadState = backgroundSync.downloadProgress;

  // ─────────────────────────────────────────────────────────────────────────
  // QUERY KEY (using data-layer utility)
  // ─────────────────────────────────────────────────────────────────────────

  const queryKeyHash = useMemo(() => hashPayloadSync(query), [query]);

  // Use data-layer's createAnalyticsQueryKey for analytics path
  const analyticsQueryKey = useMemo(
    () => createAnalyticsQueryKey('query-engine', 'query', queryKeyHash),
    [queryKeyHash],
  );

  const transactionalQueryKey = useMemo(
    () => ['query-engine', 'transactional', primaryTable, queryKeyHash] as const,
    [primaryTable, queryKeyHash],
  );

  // ─────────────────────────────────────────────────────────────────────────
  // COMPILE SQL (Analytics only)
  // ─────────────────────────────────────────────────────────────────────────

  const { compiledSql, compilationError } = useMemo((): {
    compiledSql: string | null;
    compilationError: Error | null;
  } => {
    if (!isAnalyticsPath) return { compiledSql: null, compilationError: null };
    try {
      const result = sqlCompiler.compile(query);
      return { compiledSql: result.sql, compilationError: null };
    } catch (error) {
      return {
        compiledSql: null,
        compilationError: error instanceof Error ? error : new Error(String(error)),
      };
    }
  }, [isAnalyticsPath, query, sqlCompiler]);

  // ─────────────────────────────────────────────────────────────────────────
  // ANALYTICS PATH: useDLAnalytics (data-layer hook)
  // ─────────────────────────────────────────────────────────────────────────

  const analyticsEnabled =
    enabled && isAnalyticsPath && compiledSql !== null && !downloadState.isDownloading;

  const analyticsResult = useDLAnalytics({
    sql: compiledSql ?? '',
    params: EMPTY_ARRAY,
    queryKey: analyticsQueryKey,
    enabled: analyticsEnabled,
    staleTime: staleTime ?? cacheConfig.analyticsStaleTime,
    gcTime: gcTime ?? cacheConfig.analyticsGcTime,
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TRANSACTIONAL PATH: useDLGetList (data-layer hook)
  // ─────────────────────────────────────────────────────────────────────────

  // Convert query filters to args using the new filter-converter
  const transactionalArgs = useMemo(() => {
    if (!isTransactionalPath || !primaryTable) return EMPTY_OBJECT;
    const args: Record<string, unknown> = { ...convertFiltersToArgs(query) };
    if (query.entityId) {
      args.id = query.entityId;
    }
    return args;
  }, [isTransactionalPath, primaryTable, query]);

  const wantsGet = Boolean(query.entityId) || query.operation === OPERATIONS.GET;

  // Get query descriptor from TableRegistry
  const fallbackQueryRef = useMemo(() => getAnyQueryReference(tableRegistry), [tableRegistry]);

  const getQueryRef = useMemo(() => {
    if (!primaryTable) {
      return undefined;
    }
    return getGetQueryReference(tableRegistry, primaryTable);
  }, [primaryTable, tableRegistry]);

  const listQueryRef = useMemo(() => {
    if (!primaryTable) {
      return undefined;
    }
    return getListQueryReference(tableRegistry, primaryTable);
  }, [primaryTable, tableRegistry]);

  const preferredTransactionalQueryRef = wantsGet
    ? getQueryRef ?? listQueryRef
    : listQueryRef ?? getQueryRef;

  const transactionalQueryRef =
    preferredTransactionalQueryRef ?? fallbackQueryRef ?? NOOP_QUERY_DESCRIPTOR;

  const transactionalEnabled =
    enabled &&
    isTransactionalPath &&
    !!primaryTable &&
    preferredTransactionalQueryRef !== undefined;

  const transactionalResult = useDLGet({
    query: transactionalQueryRef,
    args: transactionalArgs,
    table: primaryTable ?? '',
    entityId: wantsGet ? query.entityId : undefined,
    enabled: transactionalEnabled,
    staleTime:
      staleTime ??
      (primaryTable ? tableRegistry.getStaleTime(primaryTable) : cacheConfig.defaultStaleTime),
    gcTime:
      gcTime ?? (primaryTable ? tableRegistry.getGcTime(primaryTable) : cacheConfig.defaultGcTime),
    queryKey: transactionalQueryKey,
  });

  // ─────────────────────────────────────────────────────────────────────────
  // COMBINE RESULTS
  // ─────────────────────────────────────────────────────────────────────────

  const data = useMemo((): TData | undefined => {
    if (isAnalyticsPath) {
      const rawData = analyticsResult.rows;
      return selectQueryResultData(rawData, select);
    }
    if (isTransactionalPath) {
      const rawData = transactionalResult.data;
      if (rawData === undefined) return undefined;
      return selectQueryResultData(rawData, select);
    }
    return undefined;
  }, [
    isAnalyticsPath,
    isTransactionalPath,
    analyticsResult.rows,
    transactionalResult.data,
    select,
  ]);

  // ─────────────────────────────────────────────────────────────────────────
  // ACTIONS
  // ─────────────────────────────────────────────────────────────────────────

  const refetch = useCallback(async (): Promise<void> => {
    if (isAnalyticsPath) {
      await analyticsResult.refetch();
    } else if (isTransactionalPath) {
      await transactionalResult.refetch();
    }
  }, [isAnalyticsPath, isTransactionalPath, analyticsResult, transactionalResult]);

  const invalidate = useCallback(async (): Promise<void> => {
    const key = isAnalyticsPath ? analyticsQueryKey : transactionalQueryKey;
    await queryClient.invalidateQueries({ queryKey: key });
  }, [isAnalyticsPath, analyticsQueryKey, transactionalQueryKey, queryClient]);

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD RESULT (Discriminated Union)
  // ─────────────────────────────────────────────────────────────────────────

  const baseResult = {
    data,
    isOffline: !isOnline,
    tables: tables,
    primaryTable: primaryTable,
    refetch,
    invalidate,
  };

  // Analytics compilation error - surface immediately instead of silently pending
  if (isAnalyticsPath && compilationError !== null) {
    return {
      ...baseResult,
      executionPath: EXECUTION_PATHS.ANALYTICS,
      isLoading: false,
      isFetching: false,
      isSuccess: false,
      isError: true,
      error: compilationError,
      isStale: false,
      lastUpdatedAt: null,
      dataSource: DATA_SOURCES.NONE,
      sql: null,
      executionTimeMs: null,
      isDownloadingFiles: false as const,
      downloadProgress: 0 as const,
      filesToDownload: 0 as const,
      filesDownloaded: 0 as const,
    } satisfies UseDLQueryEngineResult<TData>;
  }

  // Analytics result
  if (isAnalyticsPath && compiledSql !== null) {
    const dataSource = analyticsResult.data ? DATA_SOURCES.DUCKDB : DATA_SOURCES.NONE;

    return {
      ...baseResult,
      executionPath: EXECUTION_PATHS.ANALYTICS,
      isLoading: analyticsResult.isLoading || downloadState.isDownloading,
      isFetching: analyticsResult.isFetching,
      isSuccess: analyticsResult.isSuccess,
      isError: analyticsResult.isError,
      error: analyticsResult.error ?? null,
      isStale: analyticsResult.isStale ?? false,
      lastUpdatedAt: analyticsResult.dataUpdatedAt ?? null,
      dataSource,
      sql: compiledSql,
      executionTimeMs: analyticsResult.executionTimeMs ?? null,
      isDownloadingFiles: downloadState.isDownloading,
      downloadProgress: downloadState.progress,
      filesToDownload: downloadState.filesTotal,
      filesDownloaded: downloadState.filesCompleted,
    } satisfies UseDLQueryEngineResult<TData>;
  }

  // Transactional result
  if (isTransactionalPath) {
    const dataSource = transactionalResult.data
      ? isOnline
        ? DATA_SOURCES.API
        : DATA_SOURCES.CACHE
      : DATA_SOURCES.NONE;

    return {
      ...baseResult,
      executionPath: EXECUTION_PATHS.TRANSACTIONAL,
      isLoading: transactionalResult.isLoading,
      isFetching: transactionalResult.isFetching,
      isSuccess: transactionalResult.isSuccess,
      isError: transactionalResult.isError,
      error: transactionalResult.error ?? null,
      isStale: transactionalResult.isStale ?? false,
      lastUpdatedAt: transactionalResult.dataUpdatedAt ?? null,
      dataSource,
      sql: null,
      executionTimeMs: null,
      isDownloadingFiles: false as const,
      downloadProgress: 0 as const,
      filesToDownload: 0 as const,
      filesDownloaded: 0 as const,
    } satisfies UseDLQueryEngineResult<TData>;
  }

  // Pending result (no decision yet)
  return {
    ...baseResult,
    executionPath: null,
    isLoading: true,
    isFetching: false,
    isSuccess: false,
    isError: false,
    error: null,
    isStale: false,
    lastUpdatedAt: null,
    dataSource: DATA_SOURCES.NONE,
    sql: null,
    executionTimeMs: null,
    isDownloadingFiles: false as const,
    downloadProgress: 0 as const,
    filesToDownload: 0 as const,
    filesDownloaded: 0 as const,
  } satisfies UseDLQueryEngineResult<TData>;
};
