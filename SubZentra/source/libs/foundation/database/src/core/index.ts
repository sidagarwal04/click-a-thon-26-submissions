/**
 * Core database exports
 * @module core
 */

export {
  InsightsDatabase,
  getDatabase,
  resetDatabase,
  hasDatabase,
  type DatabaseStats,
} from './database';

export {
  DEFAULT_DATABASE_CONFIG,
  mergeConfig,
  SYNC_STATE_KEYS,
  type DatabaseConfig,
} from './config';
