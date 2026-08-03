/**
 * Data Layer Hooks
 *
 * Clean, simplified hooks for data operations:
 * - useDLGet: Query with HTTP + offline cache fallback
 * - useDLCreate: Create with optimistic updates
 * - useDLUpdate: Update with optimistic updates
 * - useDLDelete: Delete with optimistic removal
 * - useDLAnalytics: DuckDB analytics queries
 * - useDLAnalyticsMutation: DuckDB write operations
 * - useSyncStatus: Monitor sync state
 * - useConflictResolution: Handle sync conflicts
 *
 * @module hooks
 */

export { useIsOnline } from './use-is-online';
export { useIsDuckDBAvailable } from './use-is-duckdb-available';
export { usePendingMutationCount } from './use-pending-mutation-count';

// =============================================================================
// Query Hooks
// =============================================================================

export {
  useDLGet,
  useDLGetList,
  useDLGetOne,
  type UseDLGetOptions,
  type DLGetResult,
} from './use-dl-get';

// =============================================================================
// Mutation Hooks
// =============================================================================

export { useDLCreate, type UseDLCreateOptions } from './use-dl-create';
export { useDLUpdate, type UseDLUpdateOptions } from './use-dl-update';
export { useDLDelete, type UseDLDeleteOptions } from './use-dl-delete';

// =============================================================================
// Analytics Hooks
// =============================================================================

export {
  useDLAnalytics,
  createAnalyticsQueryKey,
  type UseDLAnalyticsOptions,
  type DLAnalyticsResult,
} from './use-dl-analytics';

export {
  useDLAnalyticsMutation,
  useCreateAnalyticsView,
  useDropAnalyticsView,
  useExecuteAnalyticsSql,
  useLoadParquetFile,
  useCopyToParquet,
  type UseDLAnalyticsMutationOptions,
  type DLAnalyticsMutationResult,
} from './use-dl-analytics-mutation';

// =============================================================================
// Sync Status Hooks
// =============================================================================

export {
  useSyncStatus,
  useSyncTrigger,
  useSyncEventListener,
  type SyncStatus,
} from './use-sync-status';

// =============================================================================
// Conflict Resolution Hooks
// =============================================================================

export {
  useConflictResolution,
  useEntityConflict,
  type ConflictInfo,
  type ConflictResolution,
} from './use-conflict-resolution';

// NOTE: Analytics sync hooks (useBackgroundFileSync) are exported from
// the main src/index.ts directly from the analytics-sync module.
// They are not re-exported here to avoid cross-module barrel indirection.
