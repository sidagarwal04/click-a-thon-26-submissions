/**
 * @foundation/database
 *
 * Database layer using Dexie for offline persistence and TanStack Query integration.
 * Depends on: @foundation/data-model
 *
 * NOTE: JsonSerializable and related utilities should be imported directly from
 * @open-zentra/foundation-data-model
 *
 * NOTE: Generic hash functions (hashPayloadSync, hashPayloadAsync) should be
 * imported directly from @open-zentra/foundation-utils
 *
 * @packageDocumentation
 */

// ============================================================================
// Facade (used by data-layer)
// ============================================================================

export {
  DatabaseFacade,
  getDatabaseFacade,
  resetDatabaseFacade,
  hasDatabaseFacade,
} from './facade';

// ============================================================================
// Configuration (used by data-layer, bridge)
// ============================================================================

export { SYNC_STATE_KEYS } from './core/config';

// ============================================================================
// Tables (used by data-layer, sync-engine, bridge)
// ============================================================================

export {
  // Query cache (used by data-layer, sync-engine)
  createCacheEntry,
  isCacheExpired,
  type QueryCacheEntry,

  // Mutation queue (used by sync-engine, data-layer)
  createMutationEntry,
  canProcessMutation,
  type MutationQueueOperations,

  // OPFS metadata (used by bridge)
  createOpfsMetadata,
  type OpfsMetadataEntry,
  type OpfsFileSchema,

  // Sync state (used by bridge, sync-engine)
  // NOTE: NetworkStatus should be imported directly from @open-zentra/foundation-data-model
  isDuckDBViewsValue,
  isNetworkStatus,
  isRealtimeCursorStore,
  DEFAULT_NETWORK_STATUS,
  type SyncStateEntry,
} from './tables';

// ============================================================================
// Internal Foundation Library Exports
// ============================================================================
//
// ARCHITECTURE NOTE:
//
// The database library has two access patterns:
// 1. DatabaseFacade (recommended) - Provides a clean service-based API
//    Use getDatabaseFacade() for application code
//
// 2. InsightsDatabase (internal) - Raw Dexie database access
//    Use getDatabase() only in other foundation libraries (sync-engine, bridge)
//
// Both patterns share the same singleton source of truth in core/database.ts.
// If DatabaseFacade creates a database, getDatabase() returns that same instance.
//

export { InsightsDatabase, getDatabase } from './core/database';

// Services (used by bridge for type-safe state operations)
export { SyncStateService } from './services/sync-state';

// OPFS Manager (used by bridge for analytics file management)
// NOTE: Error callbacks use LegacyErrorCallback from @foundation/data-model
export {
  OpfsManager,
  getOpfsManager,
  resetOpfsManager,
  hasOpfsManager,
  type OpfsManagerConfig,
  type WriteFileOptions,
} from './opfs/manager';

// ============================================================================
// Errors (used by bridge)
// ============================================================================

export {
  // OPFS errors (used by bridge)
  OpfsNotSupportedError,
  createOpfsNotSupportedError,
  OpfsInitFailedError,
  createOpfsInitFailedError,
  // Database error base class and type guards
  DatabaseError,
  isDatabaseError,
  isQuotaExceededError,
} from './errors/database-errors';
