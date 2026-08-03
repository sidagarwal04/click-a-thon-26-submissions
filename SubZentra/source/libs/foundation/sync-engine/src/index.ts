/**
 * @foundation/sync-engine
 *
 * Offline-first sync engine with HTTP mutation replay, conflict resolution, and cross-tab sync.
 * Depends on: @foundation/database, @foundation/data-model
 *
 * NOTE: Sync-related types (ConflictStrategy, ConflictContext, ConflictResult, MergeConfig,
 * QueueStats, ProcessingResult, SyncState, SyncEventType, NetworkStatus, NetworkStatusListener,
 * CrossTabMessageType, CrossTabMessage, CrossTabMessageHandler, SyncEvent, SyncEventListener,
 * OfflineQueryContext, OfflineMutationResult, ConflictResolvableData) should be imported
 * directly from @open-zentra/foundation-data-model
 *
 * @packageDocumentation
 */

// ============================================================================
// Coordinator (used by data-layer)
// ============================================================================

export { SyncCoordinator, createSyncCoordinator } from './coordinator';

// ============================================================================
// Core Types (used by data-layer, query-engine)
// ============================================================================

export { type IQueueManager } from './core';

// ============================================================================
// Conflict Resolution (used by query-engine)
// ============================================================================

export { DEFAULT_MERGE_CONFIG } from './conflicts';
