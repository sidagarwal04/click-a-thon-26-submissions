/**
 * Mutation Helper Utilities
 *
 * Shared utilities for mutation hooks to reduce code duplication.
 * Handles common patterns like query invalidation, result building, and cache operations.
 *
 * @module utils/mutation-helpers
 */

import type {
  InvalidateQueryFilters,
  QueryClient,
  QueryKey,
  UseMutationResult,
} from '@tanstack/react-query';

import {
  hashQueryKey,
  SCHEMA_VERSION,
  toJsonSerializable,
} from '@open-zentra/foundation-data-model';
import { createCacheEntry } from '@open-zentra/foundation-database';
import type { DatabaseFacade } from '@open-zentra/foundation-database';

import { DEFAULT_CACHE_TTL } from '../core/constants';
import type { DLMutationResult } from '../core/types';

// =============================================================================
// QUERY INVALIDATION
// =============================================================================

/**
 * Invalidate multiple query keys
 *
 * Convenience wrapper to invalidate multiple query keys in parallel.
 * Commonly used in mutation onSuccess callbacks.
 *
 * @param queryClient - TanStack Query client instance
 * @param keys - Array of query keys to invalidate
 *
 * @example
 * ```ts
 * await invalidateQueries(queryClient, [['users'], ['users', '123']]);
 * ```
 */
export const invalidateQueries = async (
  queryClient: QueryClient,
  keys: QueryKey[],
  options?: Pick<InvalidateQueryFilters, 'refetchType'>,
): Promise<void> => {
  await Promise.all(
    keys.map((key) =>
      queryClient.invalidateQueries({
        queryKey: key,
        ...(options?.refetchType !== undefined ? { refetchType: options.refetchType } : {}),
      }),
    ),
  );
};

/**
 * Collect keys to invalidate for a mutation
 *
 * Builds the full list of query keys that should be invalidated,
 * combining explicit invalidateKeys with listQueryKey and optionally itemQueryKey.
 *
 * @param invalidateKeys - Explicitly specified keys to invalidate
 * @param listQueryKey - Optional list query key
 * @param itemQueryKey - Optional function to generate item query key
 * @param entityId - Entity ID for item query key generation
 * @returns Array of query keys to invalidate
 */
export const collectInvalidationKeys = (
  invalidateKeys: QueryKey[],
  listQueryKey?: QueryKey,
  itemQueryKey?: (entityId: string) => QueryKey,
  entityId?: string | null,
): QueryKey[] => {
  const keys = [...invalidateKeys];

  if (listQueryKey) {
    keys.push(listQueryKey);
  }

  if (itemQueryKey && entityId) {
    keys.push(itemQueryKey(entityId));
  }

  return keys;
};

// =============================================================================
// CACHE OPERATIONS
// =============================================================================

/**
 * Options for creating a cache entry with defaults
 */
export interface CreateCacheEntryOptions {
  /** Table name for the cache entry */
  readonly tableName: string;
  /** Whether this is offline/optimistic data */
  readonly isOfflineData: boolean;
  /** Custom TTL in milliseconds (default: 24 hours) */
  readonly ttl?: number;
}

/**
 * Create a cache entry with sensible defaults
 *
 * Wraps foundation-database's createCacheEntry with default values
 * for TTL and schema version. Automatically validates and converts
 * data to JsonSerializable.
 *
 * @param table - Table name
 * @param entityId - Entity ID
 * @param data - Data to cache (must be JSON-serializable)
 * @param options - Cache entry options
 * @returns Cache entry ready for database storage
 *
 * @example
 * ```ts
 * const entry = createCacheEntryWithDefaults('users', '123', userData, {
 *   tableName: 'users',
 *   isOfflineData: true,
 * });
 * await database.queries.set(entry);
 * ```
 */
export const createCacheEntryWithDefaults = <T>(
  table: string,
  entityId: string,
  data: T,
  options: CreateCacheEntryOptions,
) => {
  const cacheKey = hashQueryKey([table, entityId]);
  // Convert to JsonSerializable with validation
  const serializedData = toJsonSerializable(data);

  return createCacheEntry(cacheKey, [table, entityId], serializedData, {
    tableName: options.tableName,
    ttl: options.ttl ?? DEFAULT_CACHE_TTL,
    schemaVersion: SCHEMA_VERSION,
    isOfflineData: options.isOfflineData,
  });
};

/**
 * Persist data to the database cache
 *
 * Convenience function that creates and stores a cache entry.
 * Automatically validates and converts data to JsonSerializable.
 *
 * @param database - DatabaseFacade instance
 * @param table - Table name
 * @param entityId - Entity ID
 * @param data - Data to cache (must be JSON-serializable)
 * @param isOfflineData - Whether this is offline/optimistic data
 */
export const persistToCache = async <T>(
  database: DatabaseFacade,
  table: string,
  entityId: string,
  data: T,
  isOfflineData: boolean,
): Promise<void> => {
  const entry = createCacheEntryWithDefaults(table, entityId, data, {
    tableName: table,
    isOfflineData,
  });
  await database.queries.set(entry);
};

/**
 * Delete an entry from the database cache
 *
 * @param database - DatabaseFacade instance
 * @param table - Table name
 * @param entityId - Entity ID
 */
export const deleteFromCache = async (
  database: DatabaseFacade,
  table: string,
  entityId: string,
): Promise<void> => {
  const cacheKey = hashQueryKey([table, entityId]);
  await database.queries.delete(cacheKey);
};

// =============================================================================
// MUTATION RESULT BUILDING
// =============================================================================

/**
 * Options for building a mutation result
 */
export interface BuildMutationResultOptions<TData, TVariables> {
  /** Raw mutation result from useMutation */
  readonly mutationResult: UseMutationResult<TData, Error, TVariables>;
  /** Whether the mutation was queued for offline sync */
  readonly isQueued: boolean;
  /** Provisional ID for created items (null for update/delete) */
  readonly provisionalId: string | null;
  /** Whether the client is currently offline */
  readonly isOffline: boolean;
}

export interface LocalFirstMutationExecutionOptions<TData> {
  readonly isOnline: boolean;
  readonly setIsQueued: (value: boolean) => void;
  readonly queueOffline: () => Promise<void>;
  readonly executeOnline: () => Promise<TData>;
  readonly offlineResult: TData;
}

export const executeLocalFirstMutation = async <TData>(
  options: LocalFirstMutationExecutionOptions<TData>,
): Promise<TData> => {
  const { isOnline, setIsQueued, queueOffline, executeOnline, offlineResult } = options;

  if (!isOnline) {
    setIsQueued(true);
    await queueOffline();
    return offlineResult;
  }

  setIsQueued(false);
  return executeOnline();
};

/**
 * Build a standardized mutation result object
 *
 * Creates the consistent return type used by all DL mutation hooks.
 * Extracts relevant fields from TanStack's useMutation result and
 * adds data-layer specific metadata.
 *
 * @param options - Build options containing mutation result and metadata
 * @returns Standardized DLMutationResult
 *
 * @example
 * ```ts
 * return buildMutationResult({
 *   mutationResult,
 *   isQueued,
 *   provisionalId,
 *   isOffline: !isOnline,
 * });
 * ```
 */
export const buildMutationResult = <TData, TVariables>(
  options: BuildMutationResultOptions<TData, TVariables>,
): DLMutationResult<TData, TVariables> => {
  const { mutationResult, isQueued, provisionalId, isOffline } = options;

  return {
    data: mutationResult.data,
    isQueued,
    provisionalId,
    isOffline,
    isPending: mutationResult.isPending,
    isSuccess: mutationResult.isSuccess,
    isError: mutationResult.isError,
    isIdle: mutationResult.isIdle,
    error: mutationResult.error,
    mutate: mutationResult.mutate,
    mutateAsync: mutationResult.mutateAsync,
    reset: mutationResult.reset,
  };
};
