/**
 * Query cache table definitions and operations
 * @module tables/query-cache
 */

import {
  QUERY_CACHE_STATUS,
  type JsonValue,
  type QueryCacheStatus,
  type QueryKeyBase,
} from '@open-zentra/foundation-data-model';

/**
 * Query cache entry stored in Dexie
 * @template TData - Type of the cached data (defaults to JsonValue)
 */
export interface QueryCacheEntry<TData = JsonValue> {
  /** Hash of the query key (primary key) */
  queryHash: string;
  /** Original query key */
  queryKey: QueryKeyBase;
  /** Table/entity name for indexing */
  tableName: string;
  /** Cached data (serialized) */
  data: TData;
  /** When the data was last updated */
  dataUpdatedAt: number;
  /** When this cache entry expires */
  expiresAt: number;
  /** Schema version when cached */
  schemaVersion: number;
  /** Whether data came from offline storage */
  isOfflineData: boolean;
  /** ETag for server revalidation */
  etag?: string;
}

/**
 * Query cache entry with status
 * @template TData - Type of the cached data (defaults to JsonValue)
 */
export interface QueryCacheEntryWithStatus<TData = JsonValue> extends QueryCacheEntry<TData> {
  status: QueryCacheStatus;
}

/**
 * Options for getting cache entry
 */
export interface GetCacheOptions {
  /** Max age in milliseconds before considering stale */
  maxAge?: number;
  /** Whether to return stale data */
  returnStale?: boolean;
}

/**
 * Check if a cache entry is expired
 */
export const isCacheExpired = (entry: QueryCacheEntry): boolean => {
  return Date.now() > entry.expiresAt;
};

/**
 * Check if a cache entry is stale
 */
export const isCacheStale = (entry: QueryCacheEntry, staleThreshold: number): boolean => {
  const age = Date.now() - entry.dataUpdatedAt;
  return age > staleThreshold;
};

/**
 * Get cache status
 */
export const getCacheStatus = (
  entry: QueryCacheEntry,
  staleThreshold: number,
): QueryCacheStatus => {
  if (isCacheExpired(entry)) {
    return QUERY_CACHE_STATUS.EXPIRED;
  }
  if (isCacheStale(entry, staleThreshold)) {
    return QUERY_CACHE_STATUS.STALE;
  }
  return QUERY_CACHE_STATUS.FRESH;
};

/**
 * Options for creating a cache entry
 */
export interface CreateCacheEntryOptions {
  tableName: string;
  ttl: number;
  schemaVersion: number;
  isOfflineData?: boolean;
  etag?: string;
}

/**
 * Create a new cache entry
 * @template TData - Type of the cached data
 */
export const createCacheEntry = <TData = JsonValue>(
  queryHash: string,
  queryKey: QueryKeyBase,
  data: TData,
  options: CreateCacheEntryOptions,
): QueryCacheEntry<TData> => {
  const now = Date.now();

  return {
    queryHash,
    queryKey,
    tableName: options.tableName,
    data,
    dataUpdatedAt: now,
    expiresAt: now + options.ttl,
    schemaVersion: options.schemaVersion,
    isOfflineData: options.isOfflineData ?? false,
    etag: options.etag,
  };
};

/**
 * Query cache table operations interface
 */
export interface QueryCacheOperations {
  /** Get a cache entry by query hash */
  get(queryHash: string, options?: GetCacheOptions): Promise<QueryCacheEntryWithStatus | null>;
  /** Set a cache entry */
  set(entry: QueryCacheEntry): Promise<void>;
  /** Delete a cache entry */
  delete(queryHash: string): Promise<void>;
  /** Delete all entries for a table */
  deleteByTable(tableName: string): Promise<number>;
  /** Delete all expired entries */
  deleteExpired(): Promise<number>;
  /** Get all entries for a table */
  getByTable(tableName: string): Promise<QueryCacheEntry[]>;
  /** Check if entry exists and is fresh */
  hasFresh(queryHash: string): Promise<boolean>;
  /** Get total count of cache entries */
  count(): Promise<number>;
  /** Clear all cache entries */
  clear(): Promise<void>;

  // Bulk operations
  /** Get multiple cache entries by query hashes in a single operation */
  bulkGet(
    queryHashes: string[],
    options?: GetCacheOptions,
  ): Promise<(QueryCacheEntryWithStatus | null)[]>;
  /** Set multiple cache entries in a single operation */
  bulkSet(entries: QueryCacheEntry[]): Promise<void>;
  /** Delete multiple cache entries by query hashes */
  bulkDelete(queryHashes: string[]): Promise<number>;
}
