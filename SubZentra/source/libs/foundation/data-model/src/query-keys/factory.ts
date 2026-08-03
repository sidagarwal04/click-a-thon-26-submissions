/**
 * Query key factory implementations
 * @module query-keys/factory
 */

import type {
  AnalyticsQueryKey,
  EntityQueryKeyFactory,
  EntityTableName,
  QueryKeyBase,
  QueryKeyMeta,
  QueryScope,
} from './types';
import { QUERY_SCOPE } from './types';

/**
 * Create an entity query key factory
 */
export function createQueryKeys<
  TEntity extends string,
  TFilters extends Record<string, unknown> = Record<string, unknown>,
>(entity: TEntity): EntityQueryKeyFactory<TEntity, TFilters> {
  return {
    all: [entity] as const,

    list: (filters?: TFilters) => {
      if (filters && Object.keys(filters).length > 0) {
        return [entity, QUERY_SCOPE.LIST, filters] as const;
      }
      return [entity, QUERY_SCOPE.LIST] as const;
    },

    detail: (id: string) => [entity, QUERY_SCOPE.DETAIL, id] as const,

    infinite: (filters?: TFilters) => {
      if (filters && Object.keys(filters).length > 0) {
        return [entity, QUERY_SCOPE.INFINITE, filters] as const;
      }
      return [entity, QUERY_SCOPE.INFINITE] as const;
    },
  };
}

/**
 * Create an analytics query key
 */
export function createAnalyticsQueryKey(
  tables: EntityTableName | EntityTableName[],
  queryName: string,
): readonly ['analytics', string, string];
export function createAnalyticsQueryKey<TParams extends Record<string, unknown>>(
  tables: EntityTableName | EntityTableName[],
  queryName: string,
  params: TParams,
): readonly ['analytics', string, string, TParams];
export function createAnalyticsQueryKey(
  tables: EntityTableName | EntityTableName[],
  queryName: string,
  params?: Record<string, unknown>,
): AnalyticsQueryKey<Record<string, unknown>> | AnalyticsQueryKey<undefined> {
  const tablesString = Array.isArray(tables)
    ? `tables:${[...tables].sort().join(',')}`
    : `tables:${tables}`;

  const queryString = `query:${queryName}`;

  if (params && Object.keys(params).length > 0) {
    return ['analytics', tablesString, queryString, params] as const;
  }

  return ['analytics', tablesString, queryString] as const;
}

const QUERY_SCOPE_SET = new Set<string>(Object.values(QUERY_SCOPE));

const isQueryScope = (value: unknown): value is QueryScope =>
  typeof value === 'string' && QUERY_SCOPE_SET.has(value);

/**
 * Extract metadata from a query key
 */
export function extractQueryKeyMeta(queryKey: QueryKeyBase): QueryKeyMeta {
  const [first, second] = queryKey;

  // Analytics query
  if (first === 'analytics' && typeof second === 'string') {
    const tablesMatch = second.match(/^tables:(.+)$/);
    const tables = tablesMatch ? tablesMatch[1].split(',') : [];

    return {
      entity: 'analytics',
      isAnalytics: true,
      tables,
      queryKey,
    };
  }

  // Entity query
  const entity = String(first);
  const scope = isQueryScope(second) ? second : undefined;

  return {
    entity,
    scope,
    isAnalytics: false,
    queryKey,
  };
}

/**
 * Serialize a value with sorted object keys for deterministic output
 */
function serializeWithSortedKeys(value: unknown): string {
  return JSON.stringify(value, (_, val) => {
    // Sort object keys for deterministic hashing
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      return Object.keys(val)
        .sort()
        .reduce<Record<string, unknown>>((sorted, key) => {
          sorted[key] = (val as Record<string, unknown>)[key];
          return sorted;
        }, {});
    }
    return val;
  });
}

/**
 * Compute deterministic djb2 hash for a string.
 * Kept local to preserve data-model isolation from foundation-utils.
 */
function hashStringSync(value: string): string {
  let hash = 5381;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 33) ^ value.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}

/**
 * Generate a deterministic hash for a query key
 * Used as cache key in Dexie
 *
 * Note: Uses sorted keys serialization to ensure deterministic hashing
 * regardless of object property insertion order.
 *
 * Uses local djb2 hashing to keep data-model isolated from foundation-utils.
 */
export function hashQueryKey(queryKey: QueryKeyBase): string {
  const serialized = serializeWithSortedKeys(queryKey);
  return hashStringSync(serialized);
}

/**
 * Check if a query key matches a pattern
 * Used for cache invalidation
 */
export function matchesQueryKey(queryKey: QueryKeyBase, pattern: QueryKeyBase): boolean {
  if (pattern.length > queryKey.length) {
    return false;
  }

  for (let i = 0; i < pattern.length; i++) {
    const patternPart = pattern[i];
    const keyPart = queryKey[i];

    // Wildcard match
    if (patternPart === '*') {
      continue;
    }

    // Object comparison
    if (
      typeof patternPart === 'object' &&
      patternPart !== null &&
      typeof keyPart === 'object' &&
      keyPart !== null
    ) {
      // Check if pattern object is subset of key object
      const patternKeys = Object.keys(patternPart);
      const matches = patternKeys.every(
        (k) =>
          (patternPart as Record<string, unknown>)[k] === (keyPart as Record<string, unknown>)[k],
      );
      if (!matches) return false;
      continue;
    }

    // Direct comparison
    if (patternPart !== keyPart) {
      return false;
    }
  }

  return true;
}

// Pre-defined query key factories for common entities
export const userKeys = createQueryKeys<'users'>('users');
export const eventKeys = createQueryKeys<'events'>('events');
export const sessionKeys = createQueryKeys<'sessions'>('sessions');
export const tenantKeys = createQueryKeys<'tenants'>('tenants');
export const projectKeys = createQueryKeys<'projects'>('projects');
export const dashboardKeys = createQueryKeys<'dashboards'>('dashboards');
export const reportKeys = createQueryKeys<'reports'>('reports');
