/**
 * Database configuration
 * @module core/config
 */

import { SYNC_STATE_KEY } from '@open-zentra/foundation-data-model';
import { TIME_MS } from '@open-zentra/foundation-utils';

/**
 * Database configuration options
 */
export interface DatabaseConfig {
  /** Database name */
  name: string;
  /** Database version */
  version: number;
  /** Enable debug logging */
  debug: boolean;
  /** Query cache TTL in milliseconds (default: 5 minutes) */
  queryCacheTTL: number;
  /** Mutation queue max retry attempts */
  maxRetryAttempts: number;
  /** Stale data threshold in milliseconds */
  staleThreshold: number;
  /** Enable auto cleanup of expired data */
  autoCleanup: boolean;
  /** Cleanup interval in milliseconds */
  cleanupInterval: number;
  /** Maximum number of cache entries before LRU eviction (0 = no limit) */
  maxCacheEntries: number;
  /** Retention period for completed/failed mutations in milliseconds (default: 1 hour) */
  mutationRetentionMs: number;
}

// =============================================================================
// Environment Detection (Early Return Pattern)
// =============================================================================

/**
 * Check if running in development environment
 * Uses early returns for clarity and safety in browser environments
 */
const isDevelopment = (): boolean => {
  if (typeof process === 'undefined') return false;
  if (!process.env) return false;
  return process.env.NODE_ENV === 'development';
};

/**
 * Default database configuration
 */
export const DEFAULT_DATABASE_CONFIG: DatabaseConfig = {
  name: 'open-zentra-db',
  version: 1,
  debug: isDevelopment(),
  queryCacheTTL: TIME_MS.MINUTE * 5, // 5 minutes
  maxRetryAttempts: 3,
  staleThreshold: TIME_MS.MINUTE, // 1 minute
  autoCleanup: true,
  cleanupInterval: TIME_MS.MINUTE, // 1 minute
  maxCacheEntries: 1000, // Maximum cache entries before LRU eviction
  mutationRetentionMs: TIME_MS.HOUR, // 1 hour retention for completed/failed mutations
};

/**
 * Merge user config with defaults
 */
export const mergeConfig = (userConfig: Partial<DatabaseConfig> = {}): DatabaseConfig => ({
  ...DEFAULT_DATABASE_CONFIG,
  ...userConfig,
});

/**
 * Sync state keys
 */
export const SYNC_STATE_KEYS = {
  LAST_SYNC: SYNC_STATE_KEY.LAST_SYNC,
  NETWORK_STATUS: SYNC_STATE_KEY.NETWORK_STATUS,
  PENDING_COUNT: SYNC_STATE_KEY.PENDING_COUNT,
  DUCKDB_VIEWS: SYNC_STATE_KEY.DUCKDB_VIEWS,
  SCHEMA_VERSION: SYNC_STATE_KEY.SCHEMA_VERSION,
  CONFLICTS: SYNC_STATE_KEY.CONFLICTS,
  ID_MAPPINGS: SYNC_STATE_KEY.ID_MAPPINGS,
} as const;
