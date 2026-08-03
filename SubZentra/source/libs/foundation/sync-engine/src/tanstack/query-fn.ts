/**
 * TanStack Query function creators with offline support
 * @module tanstack/query-fn
 */

import type { QueryFunction } from '@tanstack/react-query';

import {
  hashQueryKey,
  OFFLINE_QUERY_SOURCE,
  SCHEMA_VERSION,
  tryToJsonSerializable,
  type OfflineQueryContext,
  type QueryKeyBase,
} from '@open-zentra/foundation-data-model';
import type { InsightsDatabase } from '@open-zentra/foundation-database';
import {
  createCacheEntry,
  getDatabase,
  isCacheExpired,
} from '@open-zentra/foundation-database';
import { createDebugLogger } from '@open-zentra/foundation-utils';

import { DEFAULT_CACHE_TTL_MS, DEFAULT_STALE_WHILE_REVALIDATE } from '../core/defaults';
import type { NetworkStatusMonitor } from '../network/index';
import { getNetworkMonitor } from '../network/index';

/**
 * Offline query function configuration
 */
export interface OfflineQueryFnConfig<TData = unknown> {
  /** Database instance */
  database?: InsightsDatabase;
  /** Network monitor instance */
  networkMonitor?: NetworkStatusMonitor;
  /** Fetch function for online mode */
  fetchFn: (queryKey: QueryKeyBase) => Promise<TData>;
  /** Cache TTL in milliseconds */
  cacheTTL?: number;
  /** Whether to return stale data while revalidating */
  staleWhileRevalidate?: boolean;
  /** Enable debug logging */
  debug?: boolean;
  /** Deserialize cached JSON value to runtime data type */
  deserializeCachedData: (value: unknown) => TData;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG = {
  cacheTTL: DEFAULT_CACHE_TTL_MS,
  staleWhileRevalidate: DEFAULT_STALE_WHILE_REVALIDATE,
  debug: false,
};

/**
 * Create an offline-aware query function
 */
export const createOfflineQueryFn = <TData = unknown>(
  config: OfflineQueryFnConfig<TData>,
): QueryFunction<TData, QueryKeyBase> => {
  const {
    fetchFn,
    cacheTTL = DEFAULT_CONFIG.cacheTTL,
    staleWhileRevalidate = DEFAULT_CONFIG.staleWhileRevalidate,
    debug = DEFAULT_CONFIG.debug,
  } = config;

  const db = config.database ?? getDatabase();
  const networkMonitor = config.networkMonitor ?? getNetworkMonitor();
  const logger = createDebugLogger('OfflineQueryFn', debug);
  const deserializeCachedData = config.deserializeCachedData;

  return async ({ queryKey }): Promise<TData> => {
    const qHash = hashQueryKey(queryKey);
    const tableName = String(queryKey[0]);

    logger.debug('Query:', queryKey, 'Hash:', qHash);

    // Try to get from cache first
    const cached = await db.queries.get(qHash);

    // If offline, return cached data or throw
    if (!networkMonitor.isOnline) {
      logger.debug('Offline mode');

      if (cached && !isCacheExpired(cached)) {
        logger.debug('Returning cached data (offline)');
        return deserializeCachedData(cached.data);
      }

      if (cached && staleWhileRevalidate) {
        logger.debug('Returning stale data (offline)');
        return deserializeCachedData(cached.data);
      }

      throw new Error('No cached data available offline');
    }

    // Online mode
    try {
      // Fetch fresh data
      logger.debug('Fetching fresh data');
      const data = await fetchFn(queryKey);

      // Use tryToJsonSerializable for safe caching - validates data can be serialized
      const serializableData = tryToJsonSerializable(data);
      if (serializableData === null) {
        logger.warn('Data cannot be safely serialized to JSON, skipping cache');
      } else {
        // Update cache with validated serializable data
        const entry = createCacheEntry(qHash, queryKey, serializableData, {
          tableName,
          ttl: cacheTTL,
          schemaVersion: SCHEMA_VERSION,
          isOfflineData: false,
        });
        await db.queries.put(entry);
        logger.debug('Data fetched and cached');
      }

      return data;
    } catch (error) {
      logger.debug('Fetch error:', error);

      // If fetch fails and we have cached data, return it
      if (cached && staleWhileRevalidate) {
        logger.debug('Returning stale data after fetch error');
        return deserializeCachedData(cached.data);
      }

      throw error;
    }
  };
};

// NOTE: OfflineQueryContext is now exported from @foundation/data-model
// Import it from there for consistency across the codebase

/**
 * Create query function with context
 */
export const createOfflineQueryFnWithContext = <TData = unknown>(
  config: OfflineQueryFnConfig<TData>,
): QueryFunction<{ data: TData; context: OfflineQueryContext }, QueryKeyBase> => {
  const baseQueryFn = createOfflineQueryFn<TData>(config);

  const db = config.database ?? getDatabase();
  const networkMonitor = config.networkMonitor ?? getNetworkMonitor();

  return async (ctx): Promise<{ data: TData; context: OfflineQueryContext }> => {
    const qHash = hashQueryKey(ctx.queryKey);
    const cached = await db.queries.get(qHash);

    const data = await baseQueryFn(ctx);

    const context: OfflineQueryContext = {
      isOffline: !networkMonitor.isOnline,
      isStale: cached
        ? Date.now() - cached.dataUpdatedAt > (config.cacheTTL ?? DEFAULT_CONFIG.cacheTTL)
        : false,
      source: !networkMonitor.isOnline
        ? OFFLINE_QUERY_SOURCE.OFFLINE_DB
        : cached && isCacheExpired(cached)
        ? OFFLINE_QUERY_SOURCE.CACHE
        : OFFLINE_QUERY_SOURCE.NETWORK,
      cachedAt: cached?.dataUpdatedAt,
    };

    return { data, context };
  };
};
