/**
 * Query key type definitions
 * @module query-keys/types
 */

import type { ValueOf } from '../types/utility';

/**
 * Base query key tuple
 */
export type QueryKeyBase = readonly unknown[];

/**
 * Entity query key structure
 * Format: [entity, scope?, filters?]
 */
export type EntityQueryKey<
  TEntity extends string = string,
  TScope extends string | undefined = string | undefined,
  TFilters extends Record<string, unknown> | undefined = Record<string, unknown> | undefined,
> = TScope extends undefined
  ? TFilters extends undefined
    ? readonly [TEntity]
    : readonly [TEntity, TFilters]
  : TFilters extends undefined
  ? readonly [TEntity, TScope]
  : readonly [TEntity, TScope, TFilters];

/**
 * Analytics query key structure
 * Format: ['analytics', tables, queryName, params?]
 */
export type AnalyticsQueryKey<
  TParams extends Record<string, unknown> | undefined = Record<string, unknown> | undefined,
> = TParams extends undefined
  ? readonly ['analytics', string, string]
  : readonly ['analytics', string, string, TParams];

/**
 * Query scope types
 */
export const QUERY_SCOPE = {
  LIST: 'list',
  DETAIL: 'detail',
  INFINITE: 'infinite',
} as const;

export type QueryScope = ValueOf<typeof QUERY_SCOPE>;

/**
 * Entity query key factory interface
 */
export interface EntityQueryKeyFactory<
  TEntity extends string,
  TFilters extends Record<string, unknown> = Record<string, unknown>,
> {
  /** All queries for this entity - ['entity'] */
  all: readonly [TEntity];

  /** List queries - ['entity', 'list'] or ['entity', 'list', filters] */
  list: (
    filters?: TFilters,
  ) =>
    | readonly [TEntity, typeof QUERY_SCOPE.LIST]
    | readonly [TEntity, typeof QUERY_SCOPE.LIST, TFilters];

  /** Detail query - ['entity', 'detail', id] */
  detail: (id: string) => readonly [TEntity, typeof QUERY_SCOPE.DETAIL, string];

  /** Infinite query - ['entity', 'infinite'] or ['entity', 'infinite', filters] */
  infinite: (
    filters?: TFilters,
  ) =>
    | readonly [TEntity, typeof QUERY_SCOPE.INFINITE]
    | readonly [TEntity, typeof QUERY_SCOPE.INFINITE, TFilters];
}

/**
 * Query hash for cache key
 */
export type QueryHash = string;

/**
 * Query key metadata for persistence
 */
export interface QueryKeyMeta {
  /** The entity this query belongs to */
  entity: string;
  /** Query scope (list, detail, infinite) */
  scope?: QueryScope;
  /** Whether this is an analytics query */
  isAnalytics: boolean;
  /** Tables involved (for analytics) */
  tables?: string[];
  /** Original query key */
  queryKey: QueryKeyBase;
}

/**
 * Table name constants for type safety
 *
 * These represent known entity tables in the application.
 */
export const TABLE_NAMES = {
  USERS: 'users',
  EVENTS: 'events',
  SESSIONS: 'sessions',
  TENANTS: 'tenants',
  PROJECTS: 'projects',
  DASHBOARDS: 'dashboards',
  REPORTS: 'reports',
  INTEGRATIONS: 'integrations',
} as const;

/**
 * Known entity table names union type
 *
 * This represents the known entity tables in the application.
 * For SQL identifiers that can be any table name, use `SqlTableName`
 * from the branded types module instead.
 */
export type EntityTableName = (typeof TABLE_NAMES)[keyof typeof TABLE_NAMES];

export type ApiEndpointPath = string;

/**
 * API query reference
 */
export interface ApiEndpointRef<TInput = unknown, TOutput = unknown> {
  path: ApiEndpointPath;
  input?: TInput;
  _output?: TOutput; // Phantom type for inference
}
