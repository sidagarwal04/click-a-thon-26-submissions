/**
 * useDLGet - Query hook with HTTP + offline cache fallback
 *
 * @module hooks/use-dl-get
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';

import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from '@tanstack/react-query';

import {
  hashQueryKey,
  SCHEMA_VERSION,
  toJsonSerializable,
  type ApiQueryDescriptor,
  type DataSource,
} from '@open-zentra/foundation-data-model';
import { createCacheEntry } from '@open-zentra/foundation-database';

import { executeQueryDescriptor } from '../core/http-descriptor';
import type { QueryDescriptorArgs, QueryDescriptorData } from '../core/types';
import { useDataLayerInternals } from '../provider/data-layer-internals-context';
import { createScopedErrorHandler } from '../utils/error-handler';
import { buildQueryKey, getDataSource } from '../utils/query-key';

export interface UseDLGetOptions<
  TQuery extends ApiQueryDescriptor,
  TData = QueryDescriptorData<TQuery>,
> {
  readonly query: TQuery;
  readonly args?: QueryDescriptorArgs<TQuery>;
  readonly table: string;
  readonly entityId?: string;
  readonly enabled?: boolean;
  readonly staleTime?: number;
  readonly gcTime?: number;
  readonly queryKey?: QueryKey;
  readonly select?: (data: QueryDescriptorData<TQuery>) => TData;
  readonly placeholderData?:
    | QueryDescriptorData<TQuery>
    | (() => QueryDescriptorData<TQuery>);
}

export interface DLGetResult<TData> extends Omit<UseQueryResult<TData, Error>, 'data'> {
  readonly data: TData | undefined;
  readonly isOffline: boolean;
  readonly dataSource: DataSource;
  readonly lastSyncedAt: number | null;
}

const handleGetError = createScopedErrorHandler('useDLGet');

export const useDLGet = <
  TQuery extends ApiQueryDescriptor,
  TData = QueryDescriptorData<TQuery>,
>(
  options: UseDLGetOptions<TQuery, TData>,
): DLGetResult<TData> => {
  const { database, isOnline, cacheConfig, axiosInstance } = useDataLayerInternals();

  const {
    query,
    args,
    table,
    entityId,
    enabled = true,
    staleTime,
    gcTime,
    queryKey: customQueryKey,
    select,
    placeholderData,
  } = options;

  type QueryData = QueryDescriptorData<TQuery>;

  const queryKey = useMemo(
    () => customQueryKey ?? buildQueryKey(table, entityId, args),
    [customQueryKey, table, entityId, args],
  );

  // Latest-value refs, so the cache-write effect below can use the current
  // database, table and cache config without re-running whenever their
  // identity changes — re-running it would rewrite the same cache entry.
  // Written after commit rather than during render: both readers (the offline
  // queryFn and the effect) run after commit, and useRef already seeds the
  // correct value for the first one.
  const databaseRef = useRef(database);
  const tableRef = useRef(table);
  const cacheConfigRef = useRef(cacheConfig);

  useEffect(() => {
    databaseRef.current = database;
    tableRef.current = table;
    cacheConfigRef.current = cacheConfig;
  }, [database, table, cacheConfig]);

  const resolvedArgs = (args ?? ({} as QueryDescriptorArgs<TQuery>)) as QueryDescriptorArgs<TQuery>;

  const onlineQueryFn = useCallback(async (): Promise<QueryData> => {
    return (await executeQueryDescriptor(axiosInstance, query, resolvedArgs)) as QueryData;
  }, [axiosInstance, query, resolvedArgs]);

  const offlineQueryFn = useCallback(async (): Promise<QueryData> => {
    const qHash = hashQueryKey(queryKey);
    const cached = await databaseRef.current.queries.get(qHash);

    if (cached?.data !== undefined) {
      return cached.data as QueryData;
    }

    throw new Error('No cached data available while offline');
  }, [queryKey]);

  const queryOptions: UseQueryOptions<QueryData, Error, TData, QueryKey> = {
    queryKey,
    queryFn: isOnline ? onlineQueryFn : offlineQueryFn,
    enabled,
    staleTime: staleTime ?? cacheConfig.defaultStaleTime,
    gcTime: gcTime ?? cacheConfig.defaultGcTime,
  };

  if (select !== undefined) {
    queryOptions.select = select;
  }

  if (placeholderData !== undefined) {
    queryOptions.placeholderData = placeholderData as UseQueryOptions<
      QueryData,
      Error,
      TData,
      QueryKey
    >['placeholderData'];
  }

  const result = useQuery(queryOptions);

  useEffect(() => {
    if (result.data === undefined || !result.isSuccess || !isOnline) {
      return;
    }

    const currentDatabase = databaseRef.current;
    const currentTable = tableRef.current;
    const currentCacheConfig = cacheConfigRef.current;

    const qHash = hashQueryKey(queryKey);
    const serializedData = toJsonSerializable(result.data);
    const entry = createCacheEntry(qHash, queryKey, serializedData, {
      tableName: currentTable,
      ttl: currentCacheConfig.defaultGcTime,
      schemaVersion: SCHEMA_VERSION,
      isOfflineData: false,
    });

    currentDatabase.queries.set(entry).catch((err) => {
      handleGetError(err, { data: { queryKey, table: currentTable } });
    });
  }, [result.data, result.isSuccess, isOnline, queryKey]);

  const dataSource = useMemo(
    () => getDataSource(result.data !== undefined, isOnline, result.isFetching),
    [result.data, isOnline, result.isFetching],
  );

  return {
    ...result,
    data: result.data,
    isOffline: !isOnline,
    dataSource,
    lastSyncedAt: result.dataUpdatedAt ?? null,
  };
};

export const useDLGetList = <
  TQuery extends ApiQueryDescriptor,
  TData = QueryDescriptorData<TQuery>,
>(
  options: Omit<UseDLGetOptions<TQuery, TData>, 'entityId'>,
): DLGetResult<TData> => useDLGet(options);

export const useDLGetOne = <
  TQuery extends ApiQueryDescriptor,
  TData = QueryDescriptorData<TQuery>,
>(
  options: UseDLGetOptions<TQuery, TData> & { entityId: string },
): DLGetResult<TData> => useDLGet(options);
