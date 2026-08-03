/**
 * Sync Coordinator - Main orchestrator for offline-first sync
 * @module coordinator
 */

import type { QueryClient } from '@tanstack/react-query';
import type { AxiosInstance } from 'axios';

import {
  CROSS_TAB_MESSAGE_TYPE,
  SYNC_EVENT_TYPE,
  type ConflictStrategy,
  type NetworkStatus,
  type ProcessingResult,
  type QueryKeyBase,
  type RealtimeConnectionSnapshot,
  type RealtimeServerMessage,
  type RealtimeSubscriptionSnapshot,
  type SyncEvent,
  type SyncEventListener,
  type SyncState,
} from '@open-zentra/foundation-data-model';
import type { InsightsDatabase } from '@open-zentra/foundation-database';
import { getDatabase } from '@open-zentra/foundation-database';
import {
  AsyncDisposable,
  CompositeDisposable,
  createDebugLogger,
  createSingletonFactory,
  Mutex,
  normalizeError,
  SafeDebounce,
  SafeTimer,
} from '@open-zentra/foundation-utils';

import type { ConflictResolver } from '../conflicts/resolver';
import { createConflictResolver } from '../conflicts/resolver';
import {
  DEFAULT_AUTO_START,
  DEFAULT_CONFLICT_STRATEGY,
  DEFAULT_ENABLE_CROSS_TAB,
  DEFAULT_SYNC_DEBOUNCE_DELAY_MS,
} from '../core/defaults';
import type {
  IConflictResolver,
  INetworkMonitor,
  IQueueManager,
  ISyncCoordinator,
  SyncTableConfig,
} from '../core/interfaces';
import type { CrossTabManager } from '../cross-tab/manager';
import { createCrossTabManager } from '../cross-tab/manager';
import { createHttpMutationAdapter, type HttpMutationAdapter } from '../http/adapter';
import type { NetworkStatusMonitor } from '../network/index';
import { createNetworkMonitor } from '../network/index';
import type { OfflineQueueManager } from '../queue/manager';
import { createQueueManager } from '../queue/manager';
import { QueueProcessor } from '../queue/processor';
import { createRealtimeEventBridge, type RealtimeEventBridge } from '../realtime/bridge';

/**
 * Sync coordinator configuration
 */
export interface SyncCoordinatorConfig {
  /** TanStack Query client */
  queryClient: QueryClient;
  /** Unified table configs used to resolve HTTP descriptors */
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
  /** Error callback for centralized error handling */
  onError?: (error: Error, context?: string) => void;
}

// NOTE: SyncEventType, SyncEvent, SyncEventListener, and SyncState are now in @foundation/data-model
// Import them from there for consistency across the codebase

/**
 * Default configuration
 */
const DEFAULT_CONFIG = {
  conflictStrategy: DEFAULT_CONFLICT_STRATEGY,
  enableCrossTab: DEFAULT_ENABLE_CROSS_TAB,
  debug: false,
};

/**
 * Debounce delay for sync requests (ms)
 * Prevents rapid-fire sync calls from overwhelming the system
 */
const SYNC_DEBOUNCE_DELAY_MS = DEFAULT_SYNC_DEBOUNCE_DELAY_MS;

/**
 * Sync Coordinator - Orchestrates offline-first data synchronization
 * with proper disposal, mutex protection, and error handling
 */
export class SyncCoordinator extends AsyncDisposable implements ISyncCoordinator {
  private queryClient: QueryClient;
  private httpMutationAdapter: HttpMutationAdapter;
  private realtimeBridge: RealtimeEventBridge;
  private db: InsightsDatabase;
  private networkMonitor: NetworkStatusMonitor;
  private queueManager: OfflineQueueManager;
  private queueProcessor: QueueProcessor | null = null;
  private conflictResolver: ConflictResolver;
  private crossTabManager: CrossTabManager | null = null;

  private config: SyncCoordinatorConfig & typeof DEFAULT_CONFIG;
  private listeners: Set<SyncEventListener> = new Set();
  private started = false;
  private lastSyncAt: number | null = null;

  // Mutex for sync operations to prevent race conditions
  private syncMutex = new Mutex();

  // Sync scheduling with SafeDebounce for proper cleanup
  private syncDebounce: SafeDebounce<[]> | null = null;
  private pendingSyncRequest = false;
  private pendingSyncTimer: SafeTimer | null = null;

  // Disposables for cleanup
  private runtimeDisposables: CompositeDisposable | null = null;
  private logger;

  constructor(config: SyncCoordinatorConfig) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.queryClient = config.queryClient;
    this.db = config.database ?? getDatabase();
    this.logger = createDebugLogger('SyncCoordinator', this.config.debug);

    this.httpMutationAdapter = createHttpMutationAdapter({
      axiosInstance: config.axiosInstance,
      tables: config.tables,
      debug: this.config.debug,
    });

    this.networkMonitor = createNetworkMonitor({
      database: this.db,
      healthCheckUrl: config.healthCheckUrl,
      healthCheckInterval: config.healthCheckInterval,
      axiosInstance: config.axiosInstance,
      debug: this.config.debug,
    });

    this.queueManager = createQueueManager({
      database: this.db,
      debug: this.config.debug,
    });

    this.conflictResolver = createConflictResolver({
      defaultStrategy: this.config.conflictStrategy,
      debug: this.config.debug,
    });

    if (this.config.enableCrossTab) {
      this.crossTabManager = createCrossTabManager({
        debug: this.config.debug,
      });
    }

    this.realtimeBridge = createRealtimeEventBridge({
      queryClient: this.queryClient,
      crossTabManager: this.crossTabManager,
      debug: this.config.debug,
    });

    this.queueProcessor = new QueueProcessor({
      queueManager: this.queueManager,
      conflictResolver: this.conflictResolver,
      executor: this.httpMutationAdapter.createMutationExecutor(),
      onSuccess: (mutation, result) => {
        this.logger.debug('Mutation succeeded:', mutation.id);
        const queryKeys: QueryKeyBase[] = [];
        if (mutation.invalidateKeys) {
          for (const keyStr of mutation.invalidateKeys) {
            try {
              const key = JSON.parse(keyStr);
              if (Array.isArray(key)) {
                queryKeys.push(key);
              }
            } catch {
              // Ignore parse errors
            }
          }
        }

        this.realtimeBridge.apply({
          table: mutation.tableName,
          queryKeys,
        });
      },
      onFailure: (mutation, error) => {
        this.logger.warn('Mutation failed:', mutation.id, error);
      },
      onConflict: (mutation) => {
        this.logger.debug('Conflict detected:', mutation.id);
        this.emit({
          type: SYNC_EVENT_TYPE.CONFLICT_DETECTED,
          timestamp: Date.now(),
          data: { conflictCount: 1 },
        });
      },
      onError: (error, mutation) => {
        this.handleError(error, mutation ? `Mutation ${mutation.id}` : 'Queue processing');
      },
      debug: this.config.debug,
    });

    // Constructor has no side effects. Use createAndStartSyncCoordinator()
    // or createSyncCoordinator({ autoStart: true }) to start automatically.
  }

  /**
   * Handle errors with optional callback
   */
  private handleError(error: unknown, context?: string): void {
    const err = normalizeError(error);
    this.logger.error(`Error in ${context ?? 'unknown'}:`, err);
    this.config.onError?.(err, context);
  }

  /**
   * Get current sync state
   */
  async getState(): Promise<SyncState> {
    this.ensureNotDisposed();
    const stats = await this.queueManager.getStats();

    return {
      isOnline: this.networkMonitor.isOnline,
      isSyncing: this.syncMutex.isLocked,
      lastSyncAt: this.lastSyncAt,
      pendingMutations: stats.pending + stats.offlineQueued,
      failedMutations: stats.failed,
      isLeader: this.crossTabManager?.isLeader ?? true, // Default to true if no cross-tab
    };
  }

  /**
   * Start the sync coordinator
   */
  async start(): Promise<void> {
    this.ensureNotDisposed();
    if (this.started) return;
    this.started = true;
    this.runtimeDisposables = new CompositeDisposable();

    this.logger.debug('Starting sync coordinator');

    // Start network monitor
    await this.networkMonitor.start();

    // Subscribe to network status changes
    const networkUnsubscribe = this.networkMonitor.subscribe(this.handleNetworkStatusChange);
    this.runtimeDisposables.addFunction(networkUnsubscribe);

    // Start cross-tab sync
    if (this.crossTabManager) {
      this.crossTabManager.start();
      this.setupCrossTabHandlers(this.runtimeDisposables);
    }

    // Initial sync if online
    if (this.networkMonitor.isOnline) {
      await this.sync().catch((error) => {
        this.handleError(error, 'Initial sync');
      });
    }

    this.logger.debug('Sync coordinator started');
  }

  /**
   * Stop the sync coordinator
   */
  stop(): void {
    if (!this.started) return;
    this.started = false;

    this.logger.debug('Stopping sync coordinator');

    // Stop network monitor
    this.networkMonitor.stop();

    // Stop cross-tab manager
    this.crossTabManager?.stop();

    // Stop queue processor if running
    this.queueProcessor?.stop();

    if (this.syncDebounce) {
      this.syncDebounce.cancel();
    }
    if (this.pendingSyncTimer) {
      this.pendingSyncTimer.dispose();
      this.pendingSyncTimer = null;
    }
    this.pendingSyncRequest = false;

    this.runtimeDisposables?.dispose();
    this.runtimeDisposables = null;

    this.logger.debug('Sync coordinator stopped');
  }

  /**
   * Schedule a debounced sync to prevent rapid-fire sync calls.
   * If a sync is already in progress, schedules another sync for when it completes.
   * Multiple calls while a sync is pending are coalesced into a single sync.
   *
   * Uses SafeDebounce for proper timer cleanup.
   */
  scheduleSync(): void {
    if (this.isDisposed) return;

    // If already have a pending request, don't schedule another
    if (this.pendingSyncRequest) {
      this.logger.debug('Sync already scheduled, coalescing request');
      return;
    }

    // Create debounce instance if needed
    if (!this.syncDebounce) {
      this.syncDebounce = new SafeDebounce({
        delay: SYNC_DEBOUNCE_DELAY_MS,
        callback: () => {
          this.pendingSyncRequest = false;

          if (this.isDisposed) return;

          this.sync().catch((error) => {
            this.handleError(error, 'Scheduled sync');
          });
        },
        debug: this.config.debug,
      });
    }

    // Mark that we have a pending request and trigger the debounce
    this.pendingSyncRequest = true;
    this.syncDebounce.call();
  }

  /**
   * Trigger a sync (flush queue) with mutex protection.
   * Uses queue-based scheduling to ensure sync requests are not lost.
   */
  async sync(): Promise<ProcessingResult | null> {
    this.ensureNotDisposed();

    // Try to acquire lock - if already syncing, schedule for later
    const release = this.syncMutex.tryAcquire();
    if (!release) {
      this.logger.debug('Already syncing, scheduling follow-up sync');
      // Don't lose the sync request - schedule it for when current sync completes
      this.pendingSyncRequest = true;
      return null;
    }

    try {
      if (!this.networkMonitor.isOnline) {
        this.logger.debug('Offline, skipping sync');
        return null;
      }

      if (!this.queueProcessor) {
        this.logger.debug('No queue processor configured');
        return null;
      }

      this.emit({ type: SYNC_EVENT_TYPE.SYNC_START, timestamp: Date.now() });
      this.crossTabManager?.notifySyncStarted();

      // Mark offline-queued mutations as pending
      await this.queueManager.markAllPending();

      // Process the queue
      const result = await this.queueProcessor.process();

      this.lastSyncAt = Date.now();

      this.emit({
        type: SYNC_EVENT_TYPE.SYNC_COMPLETE,
        timestamp: Date.now(),
        data: {
          queueResult: result,
          idMappings: result.idMappings,
        },
      });

      this.crossTabManager?.notifySyncCompleted();

      this.logger.debug('Sync complete:', result);
      return result;
    } catch (error) {
      this.emit({
        type: SYNC_EVENT_TYPE.SYNC_ERROR,
        timestamp: Date.now(),
        data: { error: normalizeError(error) },
      });

      this.handleError(error, 'Sync');
      throw error;
    } finally {
      release();

      // Check if there's a pending sync request that was scheduled while we were syncing
      if (this.pendingSyncRequest && !this.isDisposed) {
        this.pendingSyncRequest = false;
        this.logger.debug('Processing pending sync request');

        // Dispose any existing pending sync timer
        if (this.pendingSyncTimer) {
          this.pendingSyncTimer.dispose();
          this.pendingSyncTimer = null;
        }

        // Use SafeTimer with immediate execution to avoid stack overflow on rapid calls
        this.pendingSyncTimer = new SafeTimer({
          delay: 0,
          callback: () => {
            this.pendingSyncTimer = null;
            if (!this.isDisposed && this.networkMonitor.isOnline) {
              this.sync().catch((error) => {
                this.handleError(error, 'Pending sync');
              });
            }
          },
          debug: this.config.debug,
          autoStart: true,
        });
      }
    }
  }

  /**
   * Subscribe to sync events
   */
  subscribe(listener: SyncEventListener): () => void {
    this.ensureNotDisposed();
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Invalidate queries and notify other tabs
   */
  invalidateQueries(queryKeys: QueryKeyBase[]): void {
    this.ensureNotDisposed();
    for (const key of queryKeys) {
      this.queryClient.invalidateQueries({ queryKey: key });
    }
    this.crossTabManager?.invalidateQueries(queryKeys);
  }

  /**
   * Get network monitor instance
   */
  getNetworkMonitor(): INetworkMonitor {
    return this.networkMonitor;
  }

  /**
   * Get queue manager instance
   */
  getQueueManager(): IQueueManager {
    return this.queueManager;
  }

  /**
   * Get conflict resolver instance
   */
  getConflictResolver(): IConflictResolver {
    return this.conflictResolver;
  }

  /**
   * Broadcast realtime connection state to follower tabs.
   */
  broadcastRealtimeState(snapshot: RealtimeConnectionSnapshot): void {
    this.ensureNotDisposed();
    this.crossTabManager?.notifyRealtimeState(snapshot);
  }

  /**
   * Broadcast a validated realtime server message to follower tabs.
   */
  broadcastRealtimeMessage(message: RealtimeServerMessage): void {
    this.ensureNotDisposed();
    this.crossTabManager?.notifyRealtimeEvent(message);
  }

  /**
   * Broadcast realtime subscription state to follower tabs.
   */
  broadcastRealtimeSubscriptionState(snapshot: RealtimeSubscriptionSnapshot): void {
    this.ensureNotDisposed();
    this.crossTabManager?.notifyRealtimeSubscriptionState(snapshot);
  }

  /**
   * Broadcast a realtime resync request to follower tabs.
   */
  broadcastRealtimeResync(topic: string, table: string, reason: string): void {
    this.ensureNotDisposed();
    this.crossTabManager?.notifyRealtimeResync(topic, table, reason);
  }

  /**
   * Subscribe to realtime connection state broadcasts from the leader tab.
   */
  subscribeRealtimeState(listener: (snapshot: RealtimeConnectionSnapshot) => void): () => void {
    this.ensureNotDisposed();
    if (!this.crossTabManager) {
      return () => undefined;
    }

    return this.crossTabManager.subscribe(CROSS_TAB_MESSAGE_TYPE.REALTIME_STATE, (message) => {
      if (message.payload?.realtimeConnection) {
        listener(message.payload.realtimeConnection);
      }
    });
  }

  /**
   * Subscribe to validated realtime messages broadcast by the leader tab.
   */
  subscribeRealtimeMessages(listener: (message: RealtimeServerMessage) => void): () => void {
    this.ensureNotDisposed();
    if (!this.crossTabManager) {
      return () => undefined;
    }

    return this.crossTabManager.subscribe(CROSS_TAB_MESSAGE_TYPE.REALTIME_EVENT, (message) => {
      if (message.payload?.realtimeMessage) {
        listener(message.payload.realtimeMessage);
      }
    });
  }

  /**
   * Subscribe to realtime subscription state broadcasts from the leader tab.
   */
  subscribeRealtimeSubscriptionState(
    listener: (snapshot: RealtimeSubscriptionSnapshot) => void,
  ): () => void {
    this.ensureNotDisposed();
    if (!this.crossTabManager) {
      return () => undefined;
    }

    return this.crossTabManager.subscribe(
      CROSS_TAB_MESSAGE_TYPE.REALTIME_SUBSCRIPTION_STATE,
      (message) => {
        if (message.payload?.realtimeSubscription) {
          listener(message.payload.realtimeSubscription);
        }
      },
    );
  }

  /**
   * Subscribe to realtime resync requests broadcast by the leader tab.
   */
  subscribeRealtimeResync(
    listener: (payload: { topic: string; table: string; reason: string }) => void,
  ): () => void {
    this.ensureNotDisposed();
    if (!this.crossTabManager) {
      return () => undefined;
    }

    return this.crossTabManager.subscribe(CROSS_TAB_MESSAGE_TYPE.REALTIME_RESYNC, (message) => {
      const topic = message.payload?.topic;
      const table = message.payload?.tableName;
      const reason = message.payload?.reason;
      if (topic && table && reason) {
        listener({ topic, table, reason });
      }
    });
  }

  /**
   * Publish a realtime-originated sync event to sync listeners.
   */
  reportRealtimeEvent(event: Omit<SyncEvent, 'timestamp'> & { timestamp?: number }): void {
    this.ensureNotDisposed();
    this.emit({
      ...event,
      timestamp: event.timestamp ?? Date.now(),
    });
  }

  /**
   * Async dispose implementation
   */
  protected async onDisposeAsync(): Promise<void> {
    this.stop();

    // Dispose any pending sync timers
    if (this.syncDebounce) {
      this.syncDebounce.dispose();
      this.syncDebounce = null;
    }
    if (this.pendingSyncTimer) {
      this.pendingSyncTimer.dispose();
      this.pendingSyncTimer = null;
    }
    this.pendingSyncRequest = false;

    this.listeners.clear();
    this.runtimeDisposables = null;

    // Dispose child components
    await this.networkMonitor.disposeAsync();
    this.queueManager.dispose();
    this.conflictResolver.dispose();
    this.crossTabManager?.dispose();
    this.queueProcessor?.dispose();
    this.realtimeBridge.dispose();
    this.httpMutationAdapter.dispose();

    this.logger.debug('Disposed');
  }

  /**
   * Handle network status changes with error boundaries
   */
  private handleNetworkStatusChange = (status: NetworkStatus | { isOnline: boolean }): void => {
    if (this.isDisposed) return;

    if (status.isOnline) {
      this.logger.debug('Network online');
      this.emit({ type: SYNC_EVENT_TYPE.ONLINE, timestamp: Date.now() });
      this.crossTabManager?.notifyOnline();

      // Only sync if we're the leader (or no cross-tab)
      const shouldSync = !this.crossTabManager || this.crossTabManager.isLeader;
      if (shouldSync) {
        // Use debounced sync to prevent rapid-fire syncs during network flapping
        this.scheduleSync();
      }
    } else {
      this.logger.debug('Network offline');
      this.emit({ type: SYNC_EVENT_TYPE.OFFLINE, timestamp: Date.now() });
      this.crossTabManager?.notifyOffline();

      // Cancel any pending sync since we're now offline
      if (this.syncDebounce) {
        this.syncDebounce.cancel();
      }
      this.pendingSyncRequest = false;

      // Mark pending mutations as offline-queued
      this.queueManager.markAllOfflineQueued().catch((error) => {
        this.handleError(error, 'Mark offline queued');
      });

      // NOTE: Do NOT mutate global TanStack Query defaults here.
      // Per-query networkMode is already set to 'offlineFirst' in the
      // DataLayerContainer's QueryClient defaults. Mutating global defaults
      // here would affect ALL queries (including non-data-layer ones) and
      // the change was never reversed when going back online.
    }
  };

  /**
   * Set up cross-tab event handlers
   */
  private setupCrossTabHandlers(disposables: CompositeDisposable): void {
    if (!this.crossTabManager) return;

    // Handle invalidation from other tabs
    const invalidateUnsub = this.crossTabManager.subscribe(
      CROSS_TAB_MESSAGE_TYPE.INVALIDATE,
      (message) => {
        if (message.payload?.queryKeys) {
          for (const key of message.payload.queryKeys) {
            if (Array.isArray(key)) {
              this.queryClient.invalidateQueries({ queryKey: key });
            }
          }
        }
      },
    );
    disposables.addFunction(invalidateUnsub);

    // Handle mutation completion from other tabs
    const mutationUnsub = this.crossTabManager.subscribe(
      CROSS_TAB_MESSAGE_TYPE.MUTATION_COMPLETED,
      (message) => {
        if (message.payload?.tableName) {
          // Invalidate queries for the affected table
          this.queryClient.invalidateQueries({
            queryKey: [message.payload.tableName],
          });
        }
      },
    );
    disposables.addFunction(mutationUnsub);

    // Handle online status from other tabs
    const onlineUnsub = this.crossTabManager.subscribe(CROSS_TAB_MESSAGE_TYPE.ONLINE, () => {
      // Another tab detected we're online, verify and sync if we're leader
      if (!this.crossTabManager?.isLeader) return;

      this.networkMonitor
        .checkConnectivity()
        .then((isOnline) => {
          if (isOnline) {
            // Use debounced sync to prevent thundering herd from multiple tabs
            this.scheduleSync();
          }
        })
        .catch((error) => {
          this.handleError(error, 'Cross-tab connectivity check');
        });
    });
    disposables.addFunction(onlineUnsub);

    // Handle leader election - emit leader-changed event and sync if we became leader
    const leaderUnsub = this.crossTabManager.subscribe(
      CROSS_TAB_MESSAGE_TYPE.LEADER_ELECTED,
      (message) => {
        const isNowLeader = message.payload?.leaderId === this.crossTabManager?.id;

        // Emit leader-changed event for consumers
        this.emit({
          type: SYNC_EVENT_TYPE.LEADER_CHANGED,
          timestamp: Date.now(),
          data: { isLeader: isNowLeader },
        });

        if (isNowLeader) {
          this.logger.debug('This tab became leader, scheduling sync');
          // Use debounced sync when becoming leader
          this.scheduleSync();
        }
      },
    );
    disposables.addFunction(leaderUnsub);
  }

  /**
   * Emit a sync event
   */
  private emit(event: SyncEvent): void {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (error) {
        this.handleError(error, 'Event listener');
      }
    }
  }
}

/**
 * Create a sync coordinator instance.
 * By default this starts synchronization unless `autoStart` is explicitly `false`.
 *
 * @param config - Sync coordinator configuration
 * @returns SyncCoordinator instance
 */
export const createSyncCoordinator = (config: SyncCoordinatorConfig): SyncCoordinator => {
  const coordinator = new SyncCoordinator(config);
  const shouldAutoStart = config.autoStart ?? DEFAULT_AUTO_START;

  if (shouldAutoStart) {
    void coordinator.start().catch((error) => {
      const normalizedError = normalizeError(error);
      if (config.onError) {
        config.onError(normalizedError, 'createSyncCoordinator.autoStart');
        return;
      }
      console.error('[SyncCoordinator] Auto-start failed:', normalizedError);
    });
  }

  return coordinator;
};

/**
 * Create and start a sync coordinator instance.
 * This is the recommended way to create a coordinator when autoStart is desired.
 *
 * This function always starts the coordinator regardless of `autoStart`.
 *
 * @param config - Sync coordinator configuration
 * @returns Promise resolving to started SyncCoordinator instance
 */
export const createAndStartSyncCoordinator = async (
  config: SyncCoordinatorConfig,
): Promise<SyncCoordinator> => {
  const coordinator = new SyncCoordinator(config);
  await coordinator.start();
  return coordinator;
};

/**
 * Singleton factory for sync coordinator
 */
const syncCoordinatorFactory = createSingletonFactory(
  (config: SyncCoordinatorConfig) => new SyncCoordinator(config),
  {
    name: 'SyncCoordinator',
    onDispose: async (instance) => {
      if (instance instanceof SyncCoordinator) {
        await instance.disposeAsync();
      }
    },
  },
);

/**
 * Get or create sync coordinator singleton instance.
 */
export const getSyncCoordinator = (config: SyncCoordinatorConfig): SyncCoordinator =>
  syncCoordinatorFactory.getInstance(config);

/**
 * Reset sync coordinator singleton (for testing).
 */
export const resetSyncCoordinator = (): void => {
  void syncCoordinatorFactory.reset();
};
