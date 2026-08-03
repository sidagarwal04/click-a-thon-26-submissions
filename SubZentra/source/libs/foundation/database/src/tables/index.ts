/**
 * Table definitions exports
 *
 * NOTE: JsonSerializable and related utilities should be imported directly from
 * @open-zentra/foundation-data-model
 *
 * @module tables
 */

// Query cache
export {
  isCacheExpired,
  isCacheStale,
  getCacheStatus,
  createCacheEntry,
  type QueryCacheEntry,
  type QueryCacheEntryWithStatus,
  type GetCacheOptions,
  type QueryCacheOperations,
} from './query-cache';

// Mutation queue
export {
  createMutationEntry,
  canProcessMutation,
  shouldRetry,
  prepareForRetry,
  type MutationQueueOperations,
} from './mutation-queue';

// OPFS metadata
export {
  createOpfsMetadata,
  sortByDependencies,
  type OpfsMetadataEntry,
  type OpfsFileSchema,
  type OpfsMetadataOperations,
} from './opfs-metadata';

// Sync state
// NOTE: SYNC_STATE_KEYS is exported from core/config (single source of truth)
// NOTE: NetworkStatus should be imported directly from @open-zentra/foundation-data-model
export {
  createSyncStateEntry,
  isLastSyncValue,
  isNetworkStatus,
  isDuckDBViewsValue,
  isRealtimeCursorStore,
  DEFAULT_NETWORK_STATUS,
  DEFAULT_DUCKDB_VIEWS,
  type SyncStateEntry,
  type SyncStateOperations,
  type GetSyncStateOptions,
} from './sync-state';

// Table sync metadata (parquet file sync tracking)
export { type TableSyncMetadataOperations } from './table-sync-metadata';
