/**
 * Internal constants shared across query-engine modules.
 *
 * @module internal/constants
 */

/**
 * Internal execution path values used across decision engine and hooks.
 */
export const QUERY_ENGINE_PATHS = {
  API: 'api',
  DUCKDB: 'duckdb',
  ANALYTICS: 'analytics',
  TRANSACTIONAL: 'transactional',
} as const;

/**
 * Mapping between hook-facing path names and decision-engine path values.
 */
export const HOOK_PATH_TO_DECISION_PATH = {
  [QUERY_ENGINE_PATHS.ANALYTICS]: QUERY_ENGINE_PATHS.DUCKDB,
  [QUERY_ENGINE_PATHS.TRANSACTIONAL]: QUERY_ENGINE_PATHS.API,
} as const;
