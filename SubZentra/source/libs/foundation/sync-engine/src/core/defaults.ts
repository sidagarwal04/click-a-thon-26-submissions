/**
 * Centralized default configuration values for the sync engine
 * @module core/defaults
 *
 * This module contains all default configuration values used throughout the sync engine.
 * Centralizing defaults ensures consistency and makes it easier to maintain and document
 * the configuration options.
 *
 * NOTE: For retry configuration, use DEFAULT_RETRY_CONFIG from @foundation/utils
 */

import { CONFLICT_STRATEGY, type ConflictStrategy } from '@open-zentra/foundation-data-model';

// ============================================================================
// Network Monitor Defaults
// ============================================================================

/**
 * Default health check URL for network connectivity checks
 */
export const DEFAULT_HEALTH_CHECK_URL = '/api/health';

/**
 * Default interval between health checks (ms)
 * @default 30000 (30 seconds)
 */
export const DEFAULT_HEALTH_CHECK_INTERVAL_MS = 30000;

/**
 * Default timeout for health check requests (ms)
 * @default 5000 (5 seconds)
 */
export const DEFAULT_HEALTH_CHECK_TIMEOUT_MS = 5000;

// ============================================================================
// Queue Manager Defaults
// ============================================================================

/**
 * Default maximum retry attempts for failed mutations
 * @default 3
 */
export const DEFAULT_MAX_RETRIES = 3;

/**
 * Default maximum number of ID mappings retained in memory
 * @default 1000
 */
export const DEFAULT_MAX_ID_MAPPINGS = 1000;

/**
 * Default TTL for ID mappings in milliseconds
 * @default 86400000 (24 hours)
 */
export const DEFAULT_ID_MAPPING_TTL_MS = 24 * 60 * 60 * 1000;

// ============================================================================
// Sync Coordinator Defaults
// ============================================================================

/**
 * Default conflict resolution strategy
 * @default CONFLICT_STRATEGY.LAST_WRITE_WINS
 */
export const DEFAULT_CONFLICT_STRATEGY: ConflictStrategy = CONFLICT_STRATEGY.LAST_WRITE_WINS;

/**
 * Default auto-start behavior for coordinator
 * @default true
 */
export const DEFAULT_AUTO_START = true;

/**
 * Default cross-tab sync enablement
 * @default true
 */
export const DEFAULT_ENABLE_CROSS_TAB = true;

/**
 * Debounce delay for sync requests (ms)
 * Prevents rapid-fire sync calls from overwhelming the system
 * @default 100
 */
export const DEFAULT_SYNC_DEBOUNCE_DELAY_MS = 100;

// ============================================================================
// Cross-Tab Manager Defaults
// ============================================================================

/**
 * Default BroadcastChannel name for cross-tab communication
 */
export const DEFAULT_CHANNEL_NAME = 'open-zentra-sync';

/**
 * Default interval between leader heartbeats (ms)
 * @default 2000 (2 seconds)
 */
export const DEFAULT_LEADER_HEARTBEAT_INTERVAL_MS = 2000;

/**
 * Default timeout before assuming leader is dead (ms)
 * @default 5000 (5 seconds)
 */
export const DEFAULT_LEADER_TIMEOUT_MS = 5000;

/**
 * Base delay for initial election (ms)
 * Tabs wait 100-500ms before starting election to avoid conflicts
 * @default 100
 */
export const DEFAULT_INITIAL_ELECTION_BASE_DELAY_MS = 100;

/**
 * Range for initial election delay variance (ms)
 * Added to base delay based on tab ID hash for staggering
 * @default 400
 */
export const DEFAULT_INITIAL_ELECTION_DELAY_RANGE_MS = 400;

/**
 * Timeout for election process (ms)
 * Must be shorter than heartbeat interval to complete before next heartbeat
 * @default 300
 */
export const DEFAULT_ELECTION_TIMEOUT_MS = 300;

/**
 * Base delay for resign-triggered election (ms)
 * @default 50
 */
export const DEFAULT_RESIGN_ELECTION_BASE_DELAY_MS = 50;

/**
 * Range for resign-triggered election delay variance (ms)
 * @default 200
 */
export const DEFAULT_RESIGN_ELECTION_DELAY_RANGE_MS = 200;

// ============================================================================
// TanStack Query Defaults
// ============================================================================

/**
 * Default cache TTL for offline queries (ms)
 * @default 300000 (5 minutes)
 */
export const DEFAULT_CACHE_TTL_MS = 5 * 60 * 1000;

/**
 * Default stale-while-revalidate enablement
 * @default true
 */
export const DEFAULT_STALE_WHILE_REVALIDATE = true;

// ============================================================================
// Realtime / transport defaults
// ============================================================================

/**
 * Default polling interval for realtime subscriptions (ms)
 * @default 5000 (5 seconds)
 */
export const DEFAULT_SUBSCRIPTION_POLL_INTERVAL_MS = 5000;

// ============================================================================
// Queue Processor Defaults
// ============================================================================

/**
 * Default batch size for processing mutations
 * @default 10
 */
export const DEFAULT_BATCH_SIZE = 10;

/**
 * Default delay between mutations (ms)
 * @default 100
 */
export const DEFAULT_DELAY_BETWEEN_MUTATIONS_MS = 100;

/**
 * Default auto-cleanup enablement for completed mutations
 * @default true
 */
export const DEFAULT_AUTO_CLEANUP = true;

// ============================================================================
// Merge Config Defaults
// ============================================================================

/**
 * Default fields where server always wins in merge conflicts
 */
export const DEFAULT_SERVER_WINS_FIELDS = ['id', 'createdAt', 'tenantId'];

/**
 * Default fields where client always wins in merge conflicts
 */
export const DEFAULT_CLIENT_WINS_FIELDS: string[] = [];
