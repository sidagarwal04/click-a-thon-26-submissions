/**
 * Query Key Utilities
 *
 * Helpers for building and working with TanStack Query keys.
 *
 * NOTE: For DataSource type, import directly from @open-zentra/foundation-data-model
 *
 * @module utils/query-key
 */

import type { QueryKey } from '@tanstack/react-query';

import { DATA_SOURCE, type DataSource } from '@open-zentra/foundation-data-model';

/**
 * Build a query key from table, entityId, and args
 *
 * @example
 * ```ts
 * // List query: ['users']
 * buildQueryKey('users');
 *
 * // Single item: ['users', '123']
 * buildQueryKey('users', '123');
 *
 * // With args: ['users', { limit: 10 }]
 * buildQueryKey('users', undefined, { limit: 10 });
 * ```
 */
export const buildQueryKey = (table: string, entityId?: string, args?: unknown): QueryKey => {
  const key: unknown[] = [table];
  if (entityId) key.push(entityId);
  if (args) key.push(args);
  return key;
};

/**
 * Determine the data source based on current query state
 *
 * @param hasData - Whether the query has data
 * @param isOnline - Whether the client is online
 * @param isFetching - Whether a fetch is in progress
 * @returns The data source: 'api', 'cache', or 'none'
 */
export const getDataSource = (
  hasData: boolean,
  isOnline: boolean,
  isFetching: boolean,
): DataSource => {
  if (!hasData) return DATA_SOURCE.NONE;
  if (!isOnline) return DATA_SOURCE.CACHE;
  if (isFetching) return DATA_SOURCE.CACHE;
  return DATA_SOURCE.API;
};
