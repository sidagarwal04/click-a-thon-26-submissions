/**
 * Sync-related types for offline-first data synchronization
 *
 * These types are used across the sync-engine and other libraries
 * that implement offline-first data patterns.
 *
 * @module types/sync
 */

import type { IdMapping } from './base';
import type {
  RealtimeConnectionSnapshot,
  RealtimeServerMessage,
  RealtimeSubscriptionSnapshot,
} from './realtime';
import type { ValueOf } from './utility';

// =============================================================================
// Conflict Resolution Types
// =============================================================================

/**
 * Conflict resolution strategy values.
 */
export const CONFLICT_STRATEGY = {
  SERVER_WINS: 'server-wins',
  CLIENT_WINS: 'client-wins',
  LAST_WRITE_WINS: 'last-write-wins',
  MERGE: 'merge',
  MANUAL: 'manual',
} as const;

export type ConflictStrategy = ValueOf<typeof CONFLICT_STRATEGY>;

/**
 * Winner values for conflict resolution.
 */
export const CONFLICT_WINNER = {
  SERVER: 'server',
  CLIENT: 'client',
  MERGED: 'merged',
} as const;

export type ConflictWinner = ValueOf<typeof CONFLICT_WINNER>;

/**
 * Conflict context containing both versions of data
 *
 * @template T - The type of the conflicting data
 */
export interface ConflictContext<T = unknown> {
  /** Server version of the data */
  serverData: T;
  /** Server timestamp */
  serverTimestamp: number;
  /** Client (local) version of the data */
  clientData: T;
  /** Client timestamp */
  clientTimestamp: number;
  /** Table/entity name */
  tableName: string;
  /** Entity ID */
  entityId: string;
  /** Original data before any changes */
  baseData?: T;
}

/**
 * Conflict resolution result
 *
 * @template T - The type of the resolved data
 */
export interface ConflictResult<T = unknown> {
  /** Resolved data */
  resolvedData: T;
  /** Which version was chosen */
  winner: ConflictWinner;
  /** Whether manual review is recommended */
  requiresReview: boolean;
  /** Fields that were auto-merged (for merge strategy) */
  mergedFields?: string[];
  /** Fields with conflicts that couldn't be auto-resolved */
  conflictedFields?: string[];
}

/**
 * Field-level merge configuration
 */
export interface MergeConfig {
  /** Fields where server always wins */
  serverWinsFields?: string[];
  /** Fields where client always wins */
  clientWinsFields?: string[];
  /** Fields to merge by concatenation (arrays) */
  concatFields?: string[];
  /** Fields to merge by union (arrays/sets) */
  unionFields?: string[];
  /** Custom merge function for specific fields */
  customMerge?: Record<string, (server: unknown, client: unknown, base?: unknown) => unknown>;
}

// =============================================================================
// Queue Types
// =============================================================================

/**
 * Queue statistics
 */
export interface QueueStats {
  /** Number of pending mutations */
  pending: number;
  /** Number of mutations currently being processed */
  inProgress: number;
  /** Number of failed mutations */
  failed: number;
  /** Number of mutations queued while offline */
  offlineQueued: number;
  /** Total number of mutations in queue */
  total: number;
}

/**
 * Result of processing the mutation queue
 */
export interface ProcessingResult {
  /** Number of mutations processed */
  processed: number;
  /** Number of mutations that succeeded */
  succeeded: number;
  /** Number of mutations that failed */
  failed: number;
  /** Number of mutations skipped (e.g., due to dependencies) */
  skipped: number;
  /** ID mappings created (provisional ID -> server ID) */
  idMappings: IdMapping[];
}

// =============================================================================
// Sync State Types
// =============================================================================

/**
 * Current sync state
 */
export interface SyncState {
  /** Whether the device is currently online */
  isOnline: boolean;
  /** Whether a sync operation is in progress */
  isSyncing: boolean;
  /** Timestamp of last successful sync */
  lastSyncAt: number | null;
  /** Number of mutations pending sync */
  pendingMutations: number;
  /** Number of failed mutations */
  failedMutations: number;
  /** Whether this client is the sync leader (for cross-tab coordination) */
  isLeader: boolean;
}

/**
 * Sync event type values.
 */
export const SYNC_EVENT_TYPE = {
  ONLINE: 'online',
  OFFLINE: 'offline',
  SYNC_START: 'sync-start',
  SYNC_COMPLETE: 'sync-complete',
  SYNC_ERROR: 'sync-error',
  QUEUE_PROCESSED: 'queue-processed',
  CONFLICT_DETECTED: 'conflict-detected',
  LEADER_CHANGED: 'leader-changed',
  REALTIME_AUTH_FAILURE: 'realtime-auth-failure',
  REALTIME_PROTOCOL_ERROR: 'realtime-protocol-error',
  REALTIME_HEARTBEAT_TIMEOUT: 'realtime-heartbeat-timeout',
  REALTIME_RESUME_FAILED: 'realtime-resume-failed',
  REALTIME_RESYNC_REQUIRED: 'realtime-resync-required',
  REALTIME_SUBSCRIPTION_FAILED: 'realtime-subscription-failed',
} as const;

export type SyncEventType = ValueOf<typeof SYNC_EVENT_TYPE>;

// =============================================================================
// Network Types
// =============================================================================

/**
 * Network connectivity status
 *
 * Used by database (sync-state table), sync-engine (network monitor),
 * and data-layer for tracking online/offline state.
 */
export interface NetworkStatus {
  /** Whether the device is currently online */
  isOnline: boolean;
  /** Timestamp of last online state (null if never online) */
  lastOnlineAt: number | null;
  /** Timestamp of last offline state (null if never offline) */
  lastOfflineAt: number | null;
  /** Connection type (e.g., 'wifi', '4g') if available */
  connectionType?: string;
}

/**
 * Network status change listener callback type
 */
export type NetworkStatusListener = (status: NetworkStatus) => void;

// =============================================================================
// Cross-Tab Types
// =============================================================================

/**
 * Cross-tab message type values for inter-tab communication.
 */
export const CROSS_TAB_MESSAGE_TYPE = {
  INVALIDATE: 'invalidate',
  MUTATION_COMPLETED: 'mutation-completed',
  ONLINE: 'online',
  OFFLINE: 'offline',
  SYNC_STARTED: 'sync-started',
  SYNC_COMPLETED: 'sync-completed',
  CACHE_UPDATED: 'cache-updated',
  LEADER_ELECTED: 'leader-elected',
  LEADER_HEARTBEAT: 'leader-heartbeat',
  LEADER_RESIGN: 'leader-resign',
  LEADER_CANDIDATE: 'leader-candidate',
  REALTIME_STATE: 'realtime-state',
  REALTIME_EVENT: 'realtime-event',
  REALTIME_RESYNC: 'realtime-resync',
  REALTIME_SUBSCRIPTION_STATE: 'realtime-subscription-state',
} as const;

export type CrossTabMessageType = ValueOf<typeof CROSS_TAB_MESSAGE_TYPE>;

/**
 * Cross-tab message payload interface
 */
export interface CrossTabMessagePayload {
  /** Query keys to invalidate */
  queryKeys?: unknown[];
  /** Table/entity name affected */
  tableName?: string;
  /** Entity ID affected */
  entityId?: string;
  /** Mutation ID for tracking */
  mutationId?: string;
  /** Associated data */
  data?: unknown;
  /** Leader ID for leader election messages */
  leaderId?: string;
  /** Election term number for Raft-style leader election */
  term?: number;
  /** Realtime connection snapshot fanout */
  realtimeConnection?: RealtimeConnectionSnapshot;
  /** Realtime server message fanout */
  realtimeMessage?: RealtimeServerMessage;
  /** Realtime subscription state fanout */
  realtimeSubscription?: RealtimeSubscriptionSnapshot;
  /** Realtime topic identifier */
  topic?: string;
  /** Reason for resync request */
  reason?: string;
}

/**
 * Cross-tab message for inter-tab communication
 */
export interface CrossTabMessage {
  /** Message type */
  type: CrossTabMessageType;
  /** Source tab ID */
  tabId: string;
  /** Message timestamp */
  timestamp: number;
  /** Optional payload */
  payload?: CrossTabMessagePayload;
}

/**
 * Cross-tab message handler callback type
 */
export type CrossTabMessageHandler = (message: CrossTabMessage) => void;

// =============================================================================
// Sync Event Types
// =============================================================================

/**
 * Sync event emitted by the sync coordinator
 */
export interface SyncEvent {
  /** Event type */
  type: SyncEventType;
  /** Event timestamp */
  timestamp: number;
  /** Optional event data */
  data?: {
    /** Queue processing result */
    queueResult?: ProcessingResult;
    /** Error if sync failed */
    error?: Error;
    /** Number of conflicts detected */
    conflictCount?: number;
    /** ID mappings created during sync */
    idMappings?: IdMapping[];
    /** Whether this tab is the leader (for leader-changed events) */
    isLeader?: boolean;
    /** Realtime topic associated with the event */
    topic?: string;
    /** Realtime connection state snapshot */
    realtimeConnection?: RealtimeConnectionSnapshot;
    /** Realtime subscription state snapshot */
    realtimeSubscription?: RealtimeSubscriptionSnapshot;
    /** Last validated realtime server message */
    realtimeMessage?: RealtimeServerMessage;
  };
}

/**
 * Sync event listener callback type
 */
export type SyncEventListener = (event: SyncEvent) => void;

// =============================================================================
// Query Types
// =============================================================================

/**
 * Offline query source values.
 */
export const OFFLINE_QUERY_SOURCE = {
  CACHE: 'cache',
  NETWORK: 'network',
  OFFLINE_DB: 'offline_db',
} as const;

export type OfflineQuerySource = ValueOf<typeof OFFLINE_QUERY_SOURCE>;

/**
 * Offline query context with metadata
 */
export interface OfflineQueryContext {
  /** Whether the device is offline */
  isOffline: boolean;
  /** Whether the cached data is stale */
  isStale: boolean;
  /** Source of the data */
  source: OfflineQuerySource;
  /** When the data was cached */
  cachedAt?: number;
}

// =============================================================================
// Mutation Types
// =============================================================================

/**
 * Offline mutation result with metadata
 *
 * @template T - The type of the mutation data
 */
export interface OfflineMutationResult<T = unknown> {
  /** Result data (optimistic data if offline) */
  data: T | null;
  /** Whether the mutation was executed while offline */
  isOffline: boolean;
  /** Unique mutation ID */
  mutationId: string;
  /** Entity ID (may be provisional if created offline) */
  entityId: string;
  /** Whether the mutation was queued for later execution */
  queued: boolean;
}

// =============================================================================
// Type Constraints
// =============================================================================

/**
 * Constraint for data that can participate in conflict resolution
 *
 * This ensures the data has a structure that conflict resolvers can work with.
 * Used to add type safety to generic conflict resolution functions.
 */
export type ConflictResolvableData = Record<string, unknown>;
