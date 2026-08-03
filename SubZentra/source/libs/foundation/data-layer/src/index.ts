/**
 * @foundation/data-layer
 *
 * Public API surface for the data layer library.
 * Internal composition details are intentionally not exported here.
 *
 * @packageDocumentation
 */

// Provider
export {
  DataLayerProvider,
  DataLayerContext,
  useDataLayer,
  DataLayerInternalsContext,
  useDataLayerInternals,
  type DataLayerInternals,
  type DataLayerProviderProps,
  type DataLayerConfig,
  type DataLayerContextValue,
} from './provider';

// Query hooks
export {
  useDLGet,
  useDLGetList,
  useDLGetOne,
  type UseDLGetOptions,
  type DLGetResult,
} from './hooks/use-dl-get';

// Mutation hooks
export { useDLCreate, type UseDLCreateOptions } from './hooks/use-dl-create';
export { useDLUpdate, type UseDLUpdateOptions } from './hooks/use-dl-update';
export { useDLDelete, type UseDLDeleteOptions } from './hooks/use-dl-delete';

// Analytics hooks
export {
  useDLAnalytics,
  createAnalyticsQueryKey,
  type UseDLAnalyticsOptions,
  type DLAnalyticsResult,
} from './hooks/use-dl-analytics';
export {
  useDLAnalyticsMutation,
  useCreateAnalyticsView,
  useDropAnalyticsView,
  useExecuteAnalyticsSql,
  useLoadParquetFile,
  useCopyToParquet,
  type UseDLAnalyticsMutationOptions,
  type DLAnalyticsMutationResult,
} from './hooks/use-dl-analytics-mutation';

// Sync and conflict hooks
export {
  useSyncStatus,
  useSyncTrigger,
  useSyncEventListener,
  type SyncStatus,
} from './hooks/use-sync-status';
export {
  useConflictResolution,
  useEntityConflict,
  type ConflictInfo,
  type ConflictResolution,
} from './hooks/use-conflict-resolution';
export { useRealtimeSocket, type UseRealtimeSocketResult } from './realtime';

// Convenience state hooks
export { useIsOnline } from './hooks/use-is-online';
export { useIsDuckDBAvailable } from './hooks/use-is-duckdb-available';
export { usePendingMutationCount } from './hooks/use-pending-mutation-count';
export {
  useBackgroundFileSync,
  INITIAL_DOWNLOAD_STATE as BACKGROUND_SYNC_INITIAL_DOWNLOAD_STATE,
  type UseBackgroundFileSyncOptions,
  type UseBackgroundFileSyncResult,
  type BackgroundSyncState,
  type DownloadProgressState,
} from './analytics-sync';

// Core types and configuration
export type {
  CacheConfig,
  ResolvedCacheConfig,
  BaseMutationOptions,
  DLMutationResult,
  OptimisticMetadata,
  DataLayerQueryDescriptor,
  DataLayerMutationDescriptor,
  DataSourceEndpointDescriptor,
  QueryDescriptorArgs,
  QueryDescriptorData,
  MutationDescriptorArgs,
  MutationDescriptorData,
  RealtimeTicketAuthConfig,
  RealtimeSocketConfig,
  RealtimeSocketHeartbeatConfig,
  RealtimeSocketReconnectConfig,
  RealtimeSocketResumeConfig,
  RealtimeWebSocketTicket,
  RealtimeSocketLeaderMode,
  RealtimeMessageEnvelope,
  RealtimeMessageType,
  RealtimeOutboundMessage,
  RealtimeAckMessage,
  RealtimeConnectionStateSnapshot,
  RealtimeSubscriptionStateMap,
  RealtimeResumeCursorStore,
  RealtimeTopicSubscription,
} from './core/types';
export {
  DEFAULT_CACHE_TTL,
  DEFAULT_CACHE_CONFIG,
  DEFAULT_RETRY_CONFIG,
  QUERY_RETRY_MAX,
  QUERY_RETRY_DELAY_BASE_MS,
  QUERY_RETRY_DELAY_MAX_MS,
  OFFLINE_NETWORK_MODE,
  ANALYTICS_QUERY_RETRY_MAX,
  resolveCacheConfig,
  TableRegistry,
  createTableRegistry,
  REALTIME_MESSAGE_TYPES,
} from './core';

// Advanced instance composition
export {
  DataLayerContainer,
  createDataLayerContainer,
  type DataLayerDependencies,
  type DependencyFactories,
  type ContainerConfig,
} from './core/container';
