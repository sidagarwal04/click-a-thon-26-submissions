/**
 * Core interfaces for sync engine components
 *
 * This module defines the interfaces for dependency injection patterns.
 * Types are imported from @foundation/data-model for consistency.
 *
 * NOTE: NetworkStatus, NetworkStatusListener, CrossTabMessageType, CrossTabMessage,
 * CrossTabMessageHandler, SyncEvent, and SyncEventListener should be imported
 * directly from @open-zentra/foundation-data-model
 *
 * @module core/interfaces
 */

import type { QueryClient } from '@tanstack/react-query';
import type { AxiosInstance } from 'axios';

import type {
  ApiMutationDescriptor,
  ApiQueryDescriptor,
  ConflictContext,
  ConflictResult,
  ConflictStrategy,
  CreateMutationOptions,
  CrossTabMessage,
  CrossTabMessageHandler,
  CrossTabMessageType,
  IdMapping,
  MutationQueueEntry,
  MutationStatus,
  NetworkStatus,
  NetworkStatusListener,
  ProcessingResult,
  QueryKeyBase,
  QueueStats,
  RealtimeConnectionSnapshot,
  RealtimeServerMessage,
  RealtimeSubscriptionSnapshot,
  SyncEvent,
  SyncEventListener,
  SyncState,
  UnifiedTableConfig,
} from '@open-zentra/foundation-data-model';
import type { InsightsDatabase } from '@open-zentra/foundation-database';
import type { IAsyncDisposable, IDisposable } from '@open-zentra/foundation-utils';

export type SyncTableConfig = UnifiedTableConfig<ApiQueryDescriptor, ApiMutationDescriptor>;

// ============================================================================
// Network Monitor Interface
// ============================================================================

/**
 * Network monitor interface
 */
export interface INetworkMonitor extends IAsyncDisposable {
  /** Current network status */
  readonly status: NetworkStatus;
  /** Whether currently online */
  readonly isOnline: boolean;
  /** Start monitoring */
  start(): Promise<void>;
  /** Stop monitoring */
  stop(): void;
  /** Subscribe to status changes */
  subscribe(listener: NetworkStatusListener): () => void;
  /** Manual connectivity check */
  checkConnectivity(): Promise<boolean>;
}

// ============================================================================
// Queue Manager Interface
// ============================================================================

/**
 * ID Mapping Store interface
 *
 * Extracted from IQueueManager to follow Interface Segregation Principle.
 * Responsible for managing mappings between provisional (client-generated) IDs
 * and server-assigned IDs after mutations are synced.
 */
export interface IIdMappingStore {
  /** Register a mapping from provisional ID to server ID (may be async for persistence) */
  registerIdMapping(mapping: IdMapping): void | Promise<void>;
  /** Get server ID for a provisional ID */
  getServerId(provisionalId: string): string | undefined;
  /** Resolve ID - returns server ID if mapped, otherwise returns original */
  resolveId(id: string): string;
  /** Get all registered ID mappings */
  getIdMappings(): IdMapping[];
  /** Clear all ID mappings */
  clearIdMappings(): void;
  /** Resolve provisional IDs in a payload object, returning resolved payload */
  resolvePayloadIds<T extends Record<string, unknown>>(payload: T): T;
}

/**
 * Core queue operations interface
 *
 * Contains the primary queue management operations without ID mapping.
 * Use IQueueManager for the full interface including ID mapping.
 */
export interface IQueueOperations extends IDisposable {
  /** Add a mutation to the queue */
  enqueue(options: CreateMutationOptions): Promise<MutationQueueEntry>;
  /** Get mutation by ID */
  get(id: string): Promise<MutationQueueEntry | undefined>;
  /** Get all pending mutations */
  getPendingMutations(): Promise<MutationQueueEntry[]>;
  /** Get mutations by status */
  getByStatus(status: MutationStatus): Promise<MutationQueueEntry[]>;
  /** Update mutation status */
  updateStatus(
    id: string,
    status: MutationStatus,
    updates?: Partial<MutationQueueEntry>,
  ): Promise<void>;
  /** Mark mutation as in progress */
  markInProgress(id: string): Promise<void>;
  /** Mark mutation as completed */
  markCompleted(id: string, serverId?: string): Promise<void>;
  /** Mark mutation as failed */
  markFailed(id: string, error: string): Promise<void>;
  /** Mark all pending as offline queued */
  markAllOfflineQueued(): Promise<number>;
  /** Mark all offline queued as pending */
  markAllPending(): Promise<number>;
  /** Delete a mutation */
  delete(id: string): Promise<void>;
  /** Delete all completed mutations */
  deleteCompleted(): Promise<number>;
  /** Clear all mutations */
  clear(): Promise<void>;
  /** Get queue statistics */
  getStats(): Promise<QueueStats>;
  /** Check if there are pending mutations */
  hasPending(): Promise<boolean>;
  /** Find mutation by idempotency key */
  findByIdempotencyKey(key: string): Promise<MutationQueueEntry | undefined>;
}

/**
 * Full queue manager interface
 *
 * Combines queue operations with ID mapping functionality.
 * This is the interface typically used by consumers that need both capabilities.
 *
 * @example
 * // If you only need ID mapping, use IIdMappingStore
 * function resolveIds(store: IIdMappingStore) { ... }
 *
 * // If you only need queue operations, use IQueueOperations
 * function processQueue(queue: IQueueOperations) { ... }
 *
 * // IQueueManager provides both for convenience
 * const manager: IQueueManager = new OfflineQueueManager();
 */
export interface IQueueManager extends IQueueOperations, IIdMappingStore {
  // Combined interface - inherits from both IQueueOperations and IIdMappingStore
}

// ============================================================================
// Conflict Resolver Interface
// ============================================================================

/**
 * Conflict resolver interface
 */
export interface IConflictResolver extends IDisposable {
  /** Get strategy for a table */
  getStrategy(tableName: string): ConflictStrategy;
  /** Resolve a conflict */
  resolve<T>(context: ConflictContext<T>): ConflictResult<T>;
  /** Check if there's a conflict */
  hasConflict<T>(
    serverData: T,
    clientData: T,
    serverTimestamp: number,
    clientTimestamp: number,
  ): boolean;
  /** Set strategy for a table */
  setTableStrategy(tableName: string, strategy: ConflictStrategy): void;
}

// ============================================================================
// Cross-Tab Manager Interface
// ============================================================================

/**
 * Cross-tab manager interface
 */
export interface ICrossTabManager extends IDisposable {
  /** Tab ID */
  readonly id: string;
  /** Whether this tab is the leader */
  readonly isLeader: boolean;
  /** Start the manager */
  start(): void;
  /** Stop the manager */
  stop(): void;
  /** Subscribe to a message type */
  subscribe(type: CrossTabMessageType, handler: CrossTabMessageHandler): () => void;
  /** Broadcast a message */
  broadcast(type: CrossTabMessageType, payload?: CrossTabMessage['payload']): void;
  /** Invalidate queries across tabs */
  invalidateQueries(queryKeys: QueryKeyBase[]): void;
  /** Notify mutation completed */
  notifyMutationCompleted(
    tableName: string,
    entityId: string,
    mutationId: string,
    data?: unknown,
  ): void;
  /** Notify online */
  notifyOnline(): void;
  /** Notify offline */
  notifyOffline(): void;
  /** Notify sync started */
  notifySyncStarted(): void;
  /** Notify sync completed */
  notifySyncCompleted(): void;
  /** Broadcast realtime connection state */
  notifyRealtimeState(snapshot: RealtimeConnectionSnapshot): void;
  /** Broadcast a validated realtime server message */
  notifyRealtimeEvent(message: RealtimeServerMessage): void;
  /** Broadcast realtime subscription state */
  notifyRealtimeSubscriptionState(snapshot: RealtimeSubscriptionSnapshot): void;
  /** Broadcast a realtime resync request */
  notifyRealtimeResync(topic: string, table: string, reason: string): void;
}

// ============================================================================
// Sync Coordinator Interface
// ============================================================================

/**
 * Sync coordinator interface
 */
export interface ISyncCoordinator extends IAsyncDisposable {
  /** Get current sync state */
  getState(): Promise<SyncState>;
  /** Start the coordinator */
  start(): Promise<void>;
  /** Stop the coordinator */
  stop(): void;
  /** Trigger a sync */
  sync(): Promise<ProcessingResult | null>;
  /** Subscribe to sync events */
  subscribe(listener: SyncEventListener): () => void;
  /** Invalidate queries */
  invalidateQueries(queryKeys: QueryKeyBase[]): void;
  /** Get network monitor */
  getNetworkMonitor(): INetworkMonitor;
  /** Get queue manager */
  getQueueManager(): IQueueManager;
  /** Get conflict resolver */
  getConflictResolver(): IConflictResolver;
  /** Broadcast realtime connection state to follower tabs */
  broadcastRealtimeState(snapshot: RealtimeConnectionSnapshot): void;
  /** Broadcast a validated realtime server message to follower tabs */
  broadcastRealtimeMessage(message: RealtimeServerMessage): void;
  /** Broadcast realtime subscription state to follower tabs */
  broadcastRealtimeSubscriptionState(snapshot: RealtimeSubscriptionSnapshot): void;
  /** Broadcast a realtime resync request to follower tabs */
  broadcastRealtimeResync(topic: string, table: string, reason: string): void;
  /** Subscribe to realtime connection state from the leader tab */
  subscribeRealtimeState(listener: (snapshot: RealtimeConnectionSnapshot) => void): () => void;
  /** Subscribe to validated realtime messages from the leader tab */
  subscribeRealtimeMessages(listener: (message: RealtimeServerMessage) => void): () => void;
  /** Subscribe to realtime subscription state from the leader tab */
  subscribeRealtimeSubscriptionState(
    listener: (snapshot: RealtimeSubscriptionSnapshot) => void,
  ): () => void;
  /** Subscribe to realtime resync broadcasts from the leader tab */
  subscribeRealtimeResync(
    listener: (payload: { topic: string; table: string; reason: string }) => void,
  ): () => void;
  /** Publish a realtime-originated sync event to sync listeners */
  reportRealtimeEvent(event: Omit<SyncEvent, 'timestamp'> & { timestamp?: number }): void;
}

// ============================================================================
// Sync Engine Factory Interface
// ============================================================================

/**
 * Sync engine configuration
 */
export interface SyncEngineConfig {
  /** TanStack Query client */
  queryClient: QueryClient;
  /** Unified table configs used to resolve HTTP mutation descriptors */
  tables?: ReadonlyArray<SyncTableConfig>;
  /** Database instance */
  database?: InsightsDatabase;
  /** Conflict resolution strategy */
  conflictStrategy?: ConflictStrategy;
  /** Auto-start on creation */
  autoStart?: boolean;
  /** Enable cross-tab sync */
  enableCrossTab?: boolean;
  /** Health check URL */
  healthCheckUrl?: string;
  /** Health check interval */
  healthCheckInterval?: number;
  /** Shared Axios instance for mutation execution and health checks */
  axiosInstance: AxiosInstance;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Sync engine factory interface
 */
export interface ISyncEngineFactory {
  /** Create a sync coordinator */
  createCoordinator(config: SyncEngineConfig): ISyncCoordinator;
  /** Create a network monitor */
  createNetworkMonitor(config?: Partial<SyncEngineConfig>): INetworkMonitor;
  /** Create a queue manager */
  createQueueManager(config?: Partial<SyncEngineConfig>): IQueueManager;
  /** Create a conflict resolver */
  createConflictResolver(config?: Partial<SyncEngineConfig>): IConflictResolver;
  /** Create a cross-tab manager */
  createCrossTabManager(config?: Partial<SyncEngineConfig>): ICrossTabManager;
}
