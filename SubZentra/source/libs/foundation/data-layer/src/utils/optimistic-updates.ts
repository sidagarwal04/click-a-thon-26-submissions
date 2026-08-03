/**
 * Optimistic Update Utilities
 *
 * Shared utilities for optimistic updates in TanStack Query cache.
 * Used by useDLCreate, useDLUpdate, and useDLDelete hooks.
 *
 * @module utils/optimistic-updates
 */

import type { QueryClient, QueryKey } from '@tanstack/react-query';

import type { WithId } from '@open-zentra/foundation-data-model';
import { matchesEntityId } from '@open-zentra/foundation-data-model';

/**
 * Optimistic context for rollback operations
 *
 * Captures the previous state of data before an optimistic update,
 * allowing rollback on mutation failure.
 */
export interface OptimisticContext<T> {
  readonly queryKey: QueryKey;
  readonly previousData: T | undefined;
}

/**
 * Create an optimistic context for rollback
 *
 * Captures the current query data before performing an optimistic update,
 * enabling restoration of the previous state if the mutation fails.
 *
 * @param queryClient - TanStack Query client instance
 * @param queryKey - Query key to capture data from
 * @returns OptimisticContext with the query key and its previous data
 *
 * @example
 * ```ts
 * const context = createOptimisticContext<User[]>(queryClient, ['users']);
 * // Perform optimistic update...
 * // On error: rollbackOptimisticUpdate(queryClient, context);
 * ```
 */
export const createOptimisticContext = <T>(
  queryClient: QueryClient,
  queryKey: QueryKey,
): OptimisticContext<T> => ({
  queryKey,
  previousData: queryClient.getQueryData<T>(queryKey),
});

/**
 * Rollback an optimistic update to previous state
 *
 * Restores the query data to its state before the optimistic update.
 * If no previous data existed, removes the query entirely.
 *
 * @param queryClient - TanStack Query client instance
 * @param context - Optimistic context from createOptimisticContext
 *
 * @example
 * ```ts
 * const context = createOptimisticContext<User[]>(queryClient, ['users']);
 * // Perform optimistic update...
 * // On mutation error:
 * rollbackOptimisticUpdate(queryClient, context);
 * ```
 */
export const rollbackOptimisticUpdate = <T>(
  queryClient: QueryClient,
  context: OptimisticContext<T>,
): void => {
  if (context.previousData !== undefined) {
    queryClient.setQueryData(context.queryKey, context.previousData);
  } else {
    queryClient.removeQueries({ queryKey: context.queryKey });
  }
};

// =============================================================================
// List Operations
// =============================================================================

/**
 * Add an item to a list optimistically
 *
 * Appends a new item to an existing list in the cache.
 * Returns context for rollback if the mutation fails.
 *
 * @param queryClient - TanStack Query client instance
 * @param queryKey - Query key of the list
 * @param item - Item to add to the list
 * @returns OptimisticContext for rollback
 *
 * @example
 * ```ts
 * const context = optimisticAddToList<User>(queryClient, ['users'], newUser);
 * ```
 */
export const optimisticAddToList = <T extends WithId>(
  queryClient: QueryClient,
  queryKey: QueryKey,
  item: T,
): OptimisticContext<T[]> => {
  const context = createOptimisticContext<T[]>(queryClient, queryKey);

  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return [item];
    return [...old, item];
  });

  return context;
};

/**
 * Remove an item from a list optimistically
 *
 * Filters out an item by ID from an existing list in the cache.
 *
 * @param queryClient - TanStack Query client instance
 * @param queryKey - Query key of the list
 * @param entityId - ID of the entity to remove
 * @returns OptimisticContext for rollback
 *
 * @example
 * ```ts
 * const context = optimisticRemoveFromList<User>(queryClient, ['users'], '123');
 * ```
 */
export const optimisticRemoveFromList = <T extends WithId>(
  queryClient: QueryClient,
  queryKey: QueryKey,
  entityId: string,
): OptimisticContext<T[]> => {
  const context = createOptimisticContext<T[]>(queryClient, queryKey);

  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return old;
    return old.filter((item) => !matchesEntityId(item, entityId));
  });

  return context;
};

/**
 * Update an item in a list optimistically
 *
 * Applies an updater function to a specific item in a list.
 *
 * @param queryClient - TanStack Query client instance
 * @param queryKey - Query key of the list
 * @param entityId - ID of the entity to update
 * @param updater - Function that receives the old item and returns the updated item
 * @returns OptimisticContext for rollback
 *
 * @example
 * ```ts
 * const context = optimisticUpdateInList<User>(
 *   queryClient,
 *   ['users'],
 *   '123',
 *   (user) => ({ ...user, name: 'New Name' })
 * );
 * ```
 */
export const optimisticUpdateInList = <T extends WithId>(
  queryClient: QueryClient,
  queryKey: QueryKey,
  entityId: string,
  updater: (item: T) => T,
): OptimisticContext<T[]> => {
  const context = createOptimisticContext<T[]>(queryClient, queryKey);

  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return old;
    return old.map((item) => (matchesEntityId(item, entityId) ? updater(item) : item));
  });

  return context;
};

// =============================================================================
// Single Item Operations
// =============================================================================

/**
 * Update a single item optimistically
 *
 * Applies an updater function to a single cached item.
 * The updater receives the current data (or undefined) and returns the new data.
 *
 * @param queryClient - TanStack Query client instance
 * @param queryKey - Query key of the item
 * @param updater - Function that receives the old data and returns the updated data
 * @returns OptimisticContext for rollback
 *
 * @example
 * ```ts
 * const context = optimisticUpdateItem<User>(
 *   queryClient,
 *   ['users', '123'],
 *   (user) => ({ ...user, name: 'Updated Name' })
 * );
 * ```
 */
export const optimisticUpdateItem = <T>(
  queryClient: QueryClient,
  queryKey: QueryKey,
  updater: (item: T | undefined) => T,
): OptimisticContext<T> => {
  const context = createOptimisticContext<T>(queryClient, queryKey);

  queryClient.setQueryData<T>(queryKey, (old) => updater(old));

  return context;
};

/**
 * Replace provisional ID with server ID in a list
 *
 * After a create mutation succeeds, updates the provisional ID
 * with the actual server-assigned ID in the canonical `id` field.
 *
 * @param queryClient - TanStack Query client instance
 * @param queryKey - Query key of the list
 * @param provisionalId - The temporary provisional ID to replace
 * @param serverId - The actual server-assigned ID
 *
 * @example
 * ```ts
 * // After server returns the actual ID
 * replaceProvisionalId<User>(queryClient, ['users'], 'prov_123', 'actual_456');
 * ```
 */
export const replaceProvisionalId = <T extends WithId>(
  queryClient: QueryClient,
  queryKey: QueryKey,
  provisionalId: string,
  serverId: string,
): void => {
  queryClient.setQueryData<T[]>(queryKey, (old) => {
    if (!old) return old;
    return old.map((item) => (matchesEntityId(item, provisionalId) ? { ...item, id: serverId } : item));
  });
};
