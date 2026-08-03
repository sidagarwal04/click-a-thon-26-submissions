/**
 * Core exports
 *
 * NOTE: For utility types (WithId, WithRequiredId, ExtractId, PartialBy, OfflineMetadata, OfflineDataSource),
 * import directly from @open-zentra/foundation-data-model.
 *
 * NOTE: For type guards (hasId, hasAnyId, getEntityId, matchesEntityId),
 * import directly from @open-zentra/foundation-data-model.
 *
 * @module core
 */

// =============================================================================
// Types
// =============================================================================

export type {
  // Configuration
  CacheConfig,
  ResolvedCacheConfig,
  DataLayerConfig,
  DataLayerContextValue,

  // Base mutation types (shared across hooks)
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
} from './types';
export { REALTIME_MESSAGE_TYPES } from './types';

// =============================================================================
// Constants
// =============================================================================

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
} from './constants';

// =============================================================================
// Table Registry
// =============================================================================

export { TableRegistry, createTableRegistry } from './table-registry';

// =============================================================================
// Container
// =============================================================================

export {
  DataLayerContainer,
  createDataLayerContainer,
  type DataLayerDependencies,
  type DependencyFactories,
  type ContainerConfig,
} from './container';
