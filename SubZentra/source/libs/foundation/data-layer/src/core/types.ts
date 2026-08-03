/**
 * Core Types for Data Layer
 *
 * Shared type definitions integrating with foundation libraries.
 * Hook-specific types are colocated with their hook files.
 *
 * NOTE: For utility types (WithId, WithRequiredId, ExtractId, PartialBy, OfflineMetadata, OfflineDataSource),
 * import directly from @open-zentra/foundation-data-model.
 *
 * NOTE: For type guards (hasId, hasAnyId, getEntityId, matchesEntityId),
 * import directly from @open-zentra/foundation-data-model.
 *
 * @module core/types
 */

import type { QueryKey } from '@tanstack/react-query';
import type { AxiosInstance } from 'axios';

import type { AuthScopeSnapshot } from '@open-zentra/foundation-auth';
import { REALTIME_SERVER_MESSAGE_TYPE } from '@open-zentra/foundation-data-model';
import type {
  ApiMutationDescriptor,
  ApiQueryDescriptor,
  ConflictStrategy,
  DataSourceResponse,
  RealtimeAckServerMessage,
  RealtimeClientMessage,
  RealtimeConnectionSnapshot,
  RealtimeCursorStore,
  RealtimeProtocolVersion,
  RealtimeServerMessage,
  RealtimeSubscriptionMap,
  RealtimeTopicDescriptor,
  UnifiedTableConfig as SharedUnifiedTableConfig,
  SyncState,
} from '@open-zentra/foundation-data-model';

type DataLayerUnifiedTableConfig = SharedUnifiedTableConfig<
  ApiQueryDescriptor,
  ApiMutationDescriptor
>;

export type DataLayerQueryDescriptor = ApiQueryDescriptor;
export type DataLayerMutationDescriptor = ApiMutationDescriptor;
export type DataSourceEndpointDescriptor = ApiQueryDescriptor<
  { tables: string[] },
  DataSourceResponse
>;

export type QueryDescriptorArgs<TQuery extends ApiQueryDescriptor> =
  TQuery extends ApiQueryDescriptor<infer TArgs, unknown> ? TArgs : never;

export type QueryDescriptorData<TQuery extends ApiQueryDescriptor> =
  TQuery extends ApiQueryDescriptor<unknown, infer TData> ? TData : never;

export type MutationDescriptorArgs<TMutation extends ApiMutationDescriptor> =
  TMutation extends ApiMutationDescriptor<infer TArgs, unknown> ? TArgs : never;

export type MutationDescriptorData<TMutation extends ApiMutationDescriptor> =
  TMutation extends ApiMutationDescriptor<unknown, infer TData> ? TData : never;

// =============================================================================
// Configuration
// =============================================================================

/**
 * Cache configuration options
 */
export interface CacheConfig {
  /** Default stale time in milliseconds (default: 5 minutes) */
  readonly defaultStaleTime?: number;
  /** Default GC time in milliseconds (default: 24 hours) */
  readonly defaultGcTime?: number;
  /** Analytics stale time in milliseconds (default: 10 minutes) */
  readonly analyticsStaleTime?: number;
  /** Analytics GC time in milliseconds (default: 1 hour) */
  readonly analyticsGcTime?: number;
}

/**
 * Resolved cache configuration with defaults applied
 */
export interface ResolvedCacheConfig {
  readonly defaultStaleTime: number;
  readonly defaultGcTime: number;
  readonly analyticsStaleTime: number;
  readonly analyticsGcTime: number;
}

export interface RealtimeSocketReconnectConfig {
  readonly enabled?: boolean;
  readonly maxAttempts?: number;
  readonly initialDelayMs?: number;
  readonly maxDelayMs?: number;
}

export interface RealtimeSocketHeartbeatConfig {
  readonly enabled?: boolean;
  readonly intervalMs?: number;
  readonly timeoutMs?: number;
}

export interface RealtimeSocketResumeConfig {
  readonly enabled?: boolean;
  readonly persistCursors?: boolean;
}

export interface RealtimeWebSocketTicket {
  readonly ticket: string;
  readonly expiresAt?: number;
  readonly queryParam?: string;
  readonly url?: string;
  readonly protocols?: string[];
}

interface RealtimeTicketAuthConfigBase {
  readonly mode: 'ticket';
  readonly queryParam?: string;
}

export type RealtimeTicketAuthConfig = RealtimeTicketAuthConfigBase &
  (
    | {
        readonly getTicket: () => Promise<string | RealtimeWebSocketTicket | null>;
        readonly ticketEndpoint?: ApiQueryDescriptor<unknown, string | RealtimeWebSocketTicket>;
      }
    | {
        readonly getTicket?: () => Promise<string | RealtimeWebSocketTicket | null>;
        readonly ticketEndpoint: ApiQueryDescriptor<unknown, string | RealtimeWebSocketTicket>;
      }
  );

export type RealtimeSocketLeaderMode = 'sync-engine' | 'standalone';

export interface RealtimeSocketConfig {
  readonly url: string;
  readonly protocols?: string[];
  readonly protocolVersion?: RealtimeProtocolVersion;
  readonly auth: RealtimeTicketAuthConfig;
  readonly heartbeat?: RealtimeSocketHeartbeatConfig;
  readonly reconnect?: RealtimeSocketReconnectConfig;
  readonly resume?: RealtimeSocketResumeConfig;
  readonly leaderMode?: RealtimeSocketLeaderMode;
  readonly requestTimeoutMs?: number;
}

export const REALTIME_MESSAGE_TYPES = REALTIME_SERVER_MESSAGE_TYPE;

export type RealtimeMessageType = RealtimeServerMessage['type'];
export type RealtimeMessageEnvelope = RealtimeServerMessage;
export type RealtimeOutboundMessage = RealtimeClientMessage;
export type RealtimeAckMessage = RealtimeAckServerMessage;
export type RealtimeConnectionStateSnapshot = RealtimeConnectionSnapshot;
export type RealtimeSubscriptionStateMap = RealtimeSubscriptionMap;
export type RealtimeResumeCursorStore = RealtimeCursorStore;
export type RealtimeTopicSubscription = RealtimeTopicDescriptor;

/**
 * Data layer configuration
 */
export interface DataLayerConfig {
  /**
   * Unified table registry - single source of truth.
   * Define table configs here and they'll be shared across:
   * - DataLayer (API calls, caching)
   * - SyncEngine (conflict resolution, offline sync)
   * - QueryEngine (routing decisions, analytics)
   */
  readonly tables?: ReadonlyArray<DataLayerUnifiedTableConfig>;

  /**
   * Global datasource endpoint descriptor for background file sync.
   *
   * This endpoint returns parquet file metadata for requested tables.
   * Used by useBackgroundFileSync hook to download analytics data files.
   */
  readonly datasourceEndpoint?: DataSourceEndpointDescriptor;

  /** Conflict resolution strategy (default: CONFLICT_STRATEGY.LAST_WRITE_WINS) */
  readonly conflictStrategy?: ConflictStrategy;

  /** Enable cross-tab sync coordination (default: true) */
  readonly enableCrossTab?: boolean;

  /** Enable DuckDB analytics (default: true) */
  readonly enableAnalytics?: boolean;

  /** Default stale time for queries in ms (default: 5 minutes) */
  readonly defaultStaleTime?: number;

  /** Default garbage collection time for queries in ms (default: 24 hours) */
  readonly defaultGcTime?: number;

  /** Cache configuration overrides */
  readonly cache?: CacheConfig;

  /** Shared Axios instance used for all networked data-layer operations */
  readonly axiosInstance: AxiosInstance;

  /** Realtime WebSocket configuration */
  readonly websocket: RealtimeSocketConfig;

  /** Enable debug logging */
  readonly debug?: boolean;

  /** Sync error callback */
  readonly onSyncError?: (error: Error, context?: string) => void;

  readonly authScope?: AuthScopeSnapshot | null;
}

// =============================================================================
// Context Types
// =============================================================================

/**
 * Public data layer context value
 */
export interface DataLayerContextValue {
  /** Whether online */
  readonly isOnline: boolean;
  /** Whether data layer is initialized */
  readonly isInitialized: boolean;
  /** Whether DuckDB is available */
  readonly isDuckDBAvailable: boolean;
  /** Whether currently syncing */
  readonly isSyncing: boolean;
  /** Number of mutations pending sync */
  readonly pendingSyncCount: number;
  /** Timestamp of last successful sync */
  readonly lastSyncedAt: number | null;
  /** Whether this tab is the sync leader (cross-tab) */
  readonly isLeader: boolean;
  /** Current sync state from coordinator */
  readonly syncState: SyncState | null;

  /** Force immediate sync */
  readonly syncNow: () => Promise<void>;
  /** Clear all cached data */
  readonly clearCache: () => Promise<void>;
}

// =============================================================================
// Mutation Types (Shared across hooks)
// =============================================================================

/**
 * Base mutation options shared across create/update/delete
 */
export interface BaseMutationOptions<
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables = MutationDescriptorArgs<TMutation>,
> {
  /** HTTP mutation descriptor */
  readonly mutation: TMutation;
  /** Table name for caching and offline queue */
  readonly table: string;
  /** Query keys to invalidate on success */
  readonly invalidateKeys?: QueryKey[];
  /** Called when mutation succeeds */
  readonly onSuccess?: (data: TData | undefined, variables: TVariables) => void | Promise<void>;
  /** Called when mutation fails */
  readonly onError?: (error: Error, variables: TVariables) => void | Promise<void>;
  /** Called when mutation settles */
  readonly onSettled?: (
    data: TData | undefined,
    error: Error | null,
    variables: TVariables,
  ) => void | Promise<void>;
}

/**
 * Result from mutation hooks
 */
export interface DLMutationResult<TData, TVariables> {
  /** The mutation result data */
  readonly data: TData | undefined;
  /** Whether mutation was queued for offline sync */
  readonly isQueued: boolean;
  /** Provisional ID for created items */
  readonly provisionalId: string | null;
  /** Whether currently offline */
  readonly isOffline: boolean;
  /** Whether mutation is pending */
  readonly isPending: boolean;
  /** Whether mutation is successful */
  readonly isSuccess: boolean;
  /** Whether mutation has error */
  readonly isError: boolean;
  /** Whether mutation is idle */
  readonly isIdle: boolean;
  /** Error if any */
  readonly error: Error | null;
  /** Mutate function */
  readonly mutate: (variables: TVariables) => void;
  /** Mutate async function */
  readonly mutateAsync: (variables: TVariables) => Promise<TData | undefined>;
  /** Reset mutation state */
  readonly reset: () => void;
}

// =============================================================================
// Data Layer Specific Types
// =============================================================================

/**
 * Optimistic metadata for mutations
 *
 * Attached to entities during optimistic updates to track sync status.
 * This is specific to data-layer's implementation.
 */
export interface OptimisticMetadata {
  /** Whether this item is pending server sync */
  readonly _isPendingSync?: boolean;
  /** Provisional ID before server assignment */
  readonly _provisionalId?: string;
  /** Timestamp when item was created locally */
  readonly _createdLocallyAt?: number;
}
