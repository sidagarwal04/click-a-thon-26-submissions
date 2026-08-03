/**
 * Core module exports
 *
 * NOTE: Sync-related types (NetworkStatus, NetworkStatusListener, CrossTabMessageType,
 * CrossTabMessage, CrossTabMessageHandler, SyncEvent, SyncEventListener) should be
 * imported directly from @open-zentra/foundation-data-model
 *
 * This module exports interfaces for dependency injection patterns.
 *
 * @module core
 */

export {
  SyncEngineContainer,
  SyncEngineFactory,
  syncEngineFactory,
  createSyncEngineContainer,
  type SyncEngineContainerConfig,
} from './container';

// Interface exports (for dependency injection patterns)
export type {
  // Network
  INetworkMonitor,
  // Queue
  IIdMappingStore,
  IQueueOperations,
  IQueueManager,
  // Conflict
  IConflictResolver,
  // Cross-tab
  ICrossTabManager,
  // Sync
  ISyncCoordinator,
  // Factory
  SyncEngineConfig,
  ISyncEngineFactory,
} from './interfaces';

// ============================================================================
// Centralized Defaults
// ============================================================================

export {
  // Network Monitor
  DEFAULT_HEALTH_CHECK_URL,
  DEFAULT_HEALTH_CHECK_INTERVAL_MS,
  DEFAULT_HEALTH_CHECK_TIMEOUT_MS,
  // Queue Manager
  DEFAULT_MAX_RETRIES,
  DEFAULT_MAX_ID_MAPPINGS,
  DEFAULT_ID_MAPPING_TTL_MS,
  // Sync Coordinator
  DEFAULT_CONFLICT_STRATEGY,
  DEFAULT_AUTO_START,
  DEFAULT_ENABLE_CROSS_TAB,
  DEFAULT_SYNC_DEBOUNCE_DELAY_MS,
  // Cross-Tab Manager
  DEFAULT_CHANNEL_NAME,
  DEFAULT_LEADER_HEARTBEAT_INTERVAL_MS,
  DEFAULT_LEADER_TIMEOUT_MS,
  DEFAULT_INITIAL_ELECTION_BASE_DELAY_MS,
  DEFAULT_INITIAL_ELECTION_DELAY_RANGE_MS,
  DEFAULT_ELECTION_TIMEOUT_MS,
  DEFAULT_RESIGN_ELECTION_BASE_DELAY_MS,
  DEFAULT_RESIGN_ELECTION_DELAY_RANGE_MS,
  // TanStack Query
  DEFAULT_CACHE_TTL_MS,
  DEFAULT_STALE_WHILE_REVALIDATE,
  // Realtime / transport
  DEFAULT_SUBSCRIPTION_POLL_INTERVAL_MS,
  // Queue Processor
  DEFAULT_BATCH_SIZE,
  DEFAULT_DELAY_BETWEEN_MUTATIONS_MS,
  DEFAULT_AUTO_CLEANUP,
  // Merge Config
  DEFAULT_SERVER_WINS_FIELDS,
  DEFAULT_CLIENT_WINS_FIELDS,
} from './defaults';

// NOTE: For retry configuration, use DEFAULT_RETRY_CONFIG from @foundation/utils
