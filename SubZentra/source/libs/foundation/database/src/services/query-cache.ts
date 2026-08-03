/**
 * Query Cache Service
 *
 * Service for managing query cache entries in the database.
 * Implements QueryCacheOperations interface.
 *
 * @module services/query-cache
 */

import { QUERY_CACHE_STATUS } from '@open-zentra/foundation-data-model';

import type {
  GetCacheOptions,
  QueryCacheEntry,
  QueryCacheEntryWithStatus,
  QueryCacheOperations,
} from '../tables/query-cache';
import { getCacheStatus, isCacheExpired } from '../tables/query-cache';
import { assertValid } from '../validation/assert-valid';
import { queryCacheEntrySchema } from '../validation/schemas';
import { BaseService } from './base';

/**
 * Query Cache Service
 * Implements QueryCacheOperations with early returns and const arrow functions
 */
export class QueryCacheService extends BaseService implements QueryCacheOperations {
  /**
   * Apply cache retrieval rules to a raw entry.
   */
  private resolveEntry = (
    entry: QueryCacheEntry | undefined,
    options?: GetCacheOptions,
  ): QueryCacheEntryWithStatus | null => {
    if (!entry) {
      return null;
    }

    const status = getCacheStatus(entry, this.config.staleThreshold);
    if (status === QUERY_CACHE_STATUS.EXPIRED && !options?.returnStale) {
      return null;
    }

    if (options?.maxAge !== undefined) {
      const age = Date.now() - entry.dataUpdatedAt;
      if (age > options.maxAge) {
        return null;
      }
    }

    return { ...entry, status };
  };

  /**
   * Get a cache entry by query hash
   *
   * Uses early return pattern. Returns `null` when:
   * - The entry doesn't exist in the cache
   * - The entry is expired and `options.returnStale` is not set
   * - The entry exceeds `options.maxAge`
   *
   * @returns The cache entry with status, or `null` if not found/invalid
   */
  get = async (
    queryHash: string,
    options?: GetCacheOptions,
  ): Promise<QueryCacheEntryWithStatus | null> => {
    const entry = await this.db.queries.get(queryHash);
    return this.resolveEntry(entry, options);
  };

  /**
   * Set a cache entry
   * Validates before write
   */
  set = async (entry: QueryCacheEntry): Promise<void> => {
    assertValid(queryCacheEntrySchema, entry, 'QueryCacheEntry');
    await this.db.queries.put(entry);
    this.log('Cache entry set:', entry.queryHash);
  };

  /**
   * Delete a cache entry by query hash
   */
  delete = async (queryHash: string): Promise<void> => {
    await this.db.queries.delete(queryHash);
    this.log('Cache entry deleted:', queryHash);
  };

  /**
   * Delete all entries for a specific table
   */
  deleteByTable = async (tableName: string): Promise<number> => {
    const count = await this.db.queries.where('tableName').equals(tableName).delete();
    this.log(`Deleted ${count} entries for table:`, tableName);
    return count;
  };

  /**
   * Delete all expired entries
   */
  deleteExpired = async (): Promise<number> => {
    const now = Date.now();
    const count = await this.db.queries.where('expiresAt').below(now).delete();
    if (count > 0) {
      this.log(`Deleted ${count} expired entries`);
    }
    return count;
  };

  /**
   * Get all entries for a specific table
   */
  getByTable = async (tableName: string): Promise<QueryCacheEntry[]> => {
    return this.db.queries.where('tableName').equals(tableName).toArray();
  };

  /**
   * Check if a fresh entry exists for a query hash
   */
  hasFresh = async (queryHash: string): Promise<boolean> => {
    const entry = await this.db.queries.get(queryHash);
    if (!entry) return false;
    return !isCacheExpired(entry);
  };

  /**
   * Get total count of cache entries
   */
  count = async (): Promise<number> => {
    return this.db.queries.count();
  };

  /**
   * Clear all cache entries
   */
  clear = async (): Promise<void> => {
    await this.db.queries.clear();
    this.log('Cache cleared');
  };

  // =========================================================================
  // Bulk Operations
  // =========================================================================

  /**
   * Get multiple cache entries by query hashes in a single operation
   *
   * Returns entries in the same order as the input hashes.
   * Missing entries are represented as null in the result array.
   *
   * @param queryHashes - Array of query hashes to retrieve
   * @param options - Cache retrieval options (applied to all entries)
   * @returns Array of cache entries (null for missing/invalid entries)
   */
  bulkGet = async (
    queryHashes: string[],
    options?: GetCacheOptions,
  ): Promise<(QueryCacheEntryWithStatus | null)[]> => {
    if (queryHashes.length === 0) return [];

    // Get all entries in one query
    const entries = await this.db.queries.bulkGet(queryHashes);
    return entries.map((entry) => this.resolveEntry(entry, options));
  };

  /**
   * Set multiple cache entries in a single operation
   * Validates all entries before writing
   */
  bulkSet = async (entries: QueryCacheEntry[]): Promise<void> => {
    if (entries.length === 0) return;

    // Validate all entries first
    for (const entry of entries) {
      assertValid(queryCacheEntrySchema, entry, 'QueryCacheEntry');
    }

    await this.db.queries.bulkPut(entries);
    this.log(`Bulk set ${entries.length} cache entries`);
  };

  /**
   * Delete multiple cache entries by query hashes
   */
  bulkDelete = async (queryHashes: string[]): Promise<number> => {
    if (queryHashes.length === 0) return 0;

    const existingEntries = await this.db.queries.bulkGet(queryHashes);
    const existingCount = existingEntries.filter((entry) => entry !== undefined).length;

    await this.db.queries.bulkDelete(queryHashes);
    this.log(`Bulk deleted ${existingCount} cache entries`);
    return existingCount;
  };
}
