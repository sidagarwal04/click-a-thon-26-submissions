/**
 * Cross-tab synchronization using BroadcastChannel with leader election
 * @module cross-tab/manager
 */

import { z } from 'zod';

import type { QueryKeyBase } from '@open-zentra/foundation-data-model';
import {
  CROSS_TAB_MESSAGE_TYPE,
  realtimeConnectionSnapshotSchema,
  realtimeServerMessageSchema,
  realtimeSubscriptionSnapshotSchema,
  type CrossTabMessage,
  type CrossTabMessageHandler,
  type CrossTabMessageType,
  type RealtimeConnectionSnapshot,
  type RealtimeServerMessage,
  type RealtimeSubscriptionSnapshot,
} from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  createSingletonFactory,
  Disposable,
  hashPayloadSync,
  ManagedInterval,
  SafeTimer,
} from '@open-zentra/foundation-utils';

import {
  DEFAULT_CHANNEL_NAME,
  DEFAULT_ELECTION_TIMEOUT_MS,
  DEFAULT_INITIAL_ELECTION_BASE_DELAY_MS,
  DEFAULT_INITIAL_ELECTION_DELAY_RANGE_MS,
  DEFAULT_LEADER_HEARTBEAT_INTERVAL_MS,
  DEFAULT_LEADER_TIMEOUT_MS,
  DEFAULT_RESIGN_ELECTION_BASE_DELAY_MS,
  DEFAULT_RESIGN_ELECTION_DELAY_RANGE_MS,
} from '../core/defaults';
import type { ICrossTabManager } from '../core/interfaces';

// ============================================================================
// Zod Schema for CrossTabMessage Validation
// ============================================================================

/**
 * All valid cross-tab message types using const values from data-model
 */
const CrossTabMessageTypeSchema = z.enum([
  CROSS_TAB_MESSAGE_TYPE.INVALIDATE,
  CROSS_TAB_MESSAGE_TYPE.MUTATION_COMPLETED,
  CROSS_TAB_MESSAGE_TYPE.ONLINE,
  CROSS_TAB_MESSAGE_TYPE.OFFLINE,
  CROSS_TAB_MESSAGE_TYPE.SYNC_STARTED,
  CROSS_TAB_MESSAGE_TYPE.SYNC_COMPLETED,
  CROSS_TAB_MESSAGE_TYPE.CACHE_UPDATED,
  CROSS_TAB_MESSAGE_TYPE.LEADER_ELECTED,
  CROSS_TAB_MESSAGE_TYPE.LEADER_HEARTBEAT,
  CROSS_TAB_MESSAGE_TYPE.LEADER_RESIGN,
  CROSS_TAB_MESSAGE_TYPE.LEADER_CANDIDATE,
  CROSS_TAB_MESSAGE_TYPE.REALTIME_STATE,
  CROSS_TAB_MESSAGE_TYPE.REALTIME_EVENT,
  CROSS_TAB_MESSAGE_TYPE.REALTIME_RESYNC,
  CROSS_TAB_MESSAGE_TYPE.REALTIME_SUBSCRIPTION_STATE,
]);

/**
 * Zod schema for CrossTabMessage payload
 */
const CrossTabMessagePayloadSchema = z
  .object({
    queryKeys: z.array(z.unknown()).optional(),
    tableName: z.string().optional(),
    entityId: z.string().optional(),
    mutationId: z.string().optional(),
    data: z.unknown().optional(),
    leaderId: z.string().optional(),
    term: z.number().optional(),
    realtimeConnection: realtimeConnectionSnapshotSchema.optional(),
    realtimeMessage: realtimeServerMessageSchema.optional(),
    realtimeSubscription: realtimeSubscriptionSnapshotSchema.optional(),
    topic: z.string().optional(),
    reason: z.string().optional(),
  })
  .optional();

/**
 * Zod schema for complete CrossTabMessage
 */
const CrossTabMessageSchema = z.object({
  type: CrossTabMessageTypeSchema,
  tabId: z.string(),
  timestamp: z.number(),
  payload: CrossTabMessagePayloadSchema,
});

/**
 * Parse and validate a CrossTabMessage with Zod
 * Returns null if validation fails
 */
const parseAndValidateCrossTabMessage = (value: unknown): CrossTabMessage | null => {
  const result = CrossTabMessageSchema.safeParse(value);
  if (!result.success) {
    return null;
  }
  return result.data;
};

/**
 * Export the schema for external use (e.g., testing)
 */
export { CrossTabMessageSchema };

// ============================================================================
// Type-safe Payload Extraction Helpers
// ============================================================================

/**
 * Leader-related payload fields
 */
interface LeaderPayload {
  leaderId: string | undefined;
  term: number;
}

/**
 * Extract leader-related fields from message payload with type safety
 * Provides default values for missing fields
 */
const extractLeaderPayload = (payload: CrossTabMessage['payload']): LeaderPayload => ({
  leaderId: typeof payload?.leaderId === 'string' ? payload.leaderId : undefined,
  term: typeof payload?.term === 'number' ? payload.term : 0,
});

/**
 * Cross-tab manager configuration
 */
export interface CrossTabManagerConfig {
  /** Channel name */
  channelName?: string;
  /** Leader heartbeat interval in ms */
  leaderHeartbeatInterval?: number;
  /** Leader timeout in ms (how long before assuming leader is dead) */
  leaderTimeout?: number;
  /** Enable debug logging */
  debug?: boolean;
  /** Error callback for centralized error handling */
  onError?: (error: Error, context?: string) => void;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<Omit<CrossTabManagerConfig, 'onError'>> = {
  channelName: DEFAULT_CHANNEL_NAME,
  leaderHeartbeatInterval: DEFAULT_LEADER_HEARTBEAT_INTERVAL_MS,
  leaderTimeout: DEFAULT_LEADER_TIMEOUT_MS,
  debug: false,
};

/**
 * Cross-tab synchronization manager with leader election
 *
 * Uses a Raft-inspired leader election algorithm with term numbers to prevent split-brain
 * scenarios. The leader is responsible for coordinating sync operations across tabs.
 */
export class CrossTabManager extends Disposable implements ICrossTabManager {
  private config: Required<Omit<CrossTabManagerConfig, 'onError'>>;
  private channel: BroadcastChannel | null = null;
  private tabId: string;
  private handlers: Map<CrossTabMessageType, Set<CrossTabMessageHandler>> = new Map();
  private started = false;
  private logger;

  // Leader election state
  private _isLeader = false;
  private currentLeaderId: string | null = null;
  private lastLeaderHeartbeat = 0;

  // Managed timers for leader heartbeat and health check
  private leaderHeartbeatTimer: SafeTimer | null = null;
  private leaderCheckInterval: ManagedInterval | null = null;

  // SafeTimers for election timeouts (prevents memory leaks)
  private initialElectionTimer: SafeTimer | null = null;
  private electionTimer: SafeTimer | null = null;
  private resignElectionTimer: SafeTimer | null = null;

  // Election term for Raft-style leader election
  // Higher term wins in case of conflicts
  private electionTerm = 0;
  private currentLeaderTerm = 0;
  private isElectionInProgress = false;

  constructor(config: CrossTabManagerConfig = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.tabId = crypto.randomUUID();
    this.logger = createDebugLogger('CrossTabManager', this.config.debug);
  }

  /**
   * Check if BroadcastChannel is supported
   */
  static isSupported(): boolean {
    return typeof BroadcastChannel !== 'undefined';
  }

  /**
   * Get the tab ID
   */
  get id(): string {
    return this.tabId;
  }

  /**
   * Check if this tab is the leader
   */
  get isLeader(): boolean {
    return this._isLeader;
  }

  /**
   * Start the cross-tab manager
   */
  start(): void {
    this.ensureNotDisposed();
    if (this.started) return;

    if (!CrossTabManager.isSupported()) {
      this.logger.warn('BroadcastChannel not supported');
      // Become leader by default when no cross-tab support
      this._isLeader = true;
      this.started = true;
      return;
    }

    this.channel = new BroadcastChannel(this.config.channelName);
    this.channel.onmessage = this.handleMessage;
    this.started = true;

    // Start leader election
    this.startLeaderElection();

    this.logger.debug('Started with tab ID:', this.tabId);
  }

  /**
   * Stop the cross-tab manager
   */
  stop(): void {
    if (!this.started) return;

    // Resign leadership if we're the leader
    if (this._isLeader) {
      this.broadcast(CROSS_TAB_MESSAGE_TYPE.LEADER_RESIGN, { leaderId: this.tabId });
      this._isLeader = false;
    }

    this.stopLeaderHeartbeat();
    this.stopLeaderCheck();

    // Dispose all pending election timers to prevent memory leaks
    this.initialElectionTimer?.dispose();
    this.initialElectionTimer = null;

    this.electionTimer?.dispose();
    this.electionTimer = null;

    this.resignElectionTimer?.dispose();
    this.resignElectionTimer = null;

    if (this.channel) {
      this.channel.onmessage = null;
      this.channel.close();
      this.channel = null;
    }

    this.started = false;
    this.logger.debug('Stopped');
  }

  /**
   * Subscribe to a message type
   */
  subscribe(type: CrossTabMessageType, handler: CrossTabMessageHandler): () => void {
    this.ensureNotDisposed();
    let handlers = this.handlers.get(type);
    if (!handlers) {
      handlers = new Set();
      this.handlers.set(type, handlers);
    }
    handlers.add(handler);

    return () => {
      handlers?.delete(handler);
      // Clean up empty Sets to prevent memory leaks
      if (handlers && handlers.size === 0) {
        this.handlers.delete(type);
      }
    };
  }

  /**
   * Get count of active subscriptions for monitoring/debugging.
   */
  getSubscriptionCount(): number {
    let count = 0;
    for (const handlers of this.handlers.values()) {
      count += handlers.size;
    }
    return count;
  }

  /**
   * Broadcast a message to other tabs
   */
  broadcast(type: CrossTabMessageType, payload?: CrossTabMessage['payload']): void {
    if (this.isDisposed) return;

    if (!this.channel) {
      this.logger.debug('Cannot broadcast - channel not open');
      return;
    }

    const message: CrossTabMessage = {
      type,
      tabId: this.tabId,
      timestamp: Date.now(),
      payload,
    };

    this.channel.postMessage(message);
    this.logger.debug('Broadcast:', type, payload);
  }

  /**
   * Broadcast query invalidation
   */
  invalidateQueries(queryKeys: QueryKeyBase[]): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.INVALIDATE, { queryKeys });
  }

  /**
   * Broadcast mutation completion
   */
  notifyMutationCompleted(
    tableName: string,
    entityId: string,
    mutationId: string,
    data?: unknown,
  ): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.MUTATION_COMPLETED, {
      tableName,
      entityId,
      mutationId,
      data,
    });
  }

  /**
   * Broadcast online status
   */
  notifyOnline(): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.ONLINE);
  }

  /**
   * Broadcast offline status
   */
  notifyOffline(): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.OFFLINE);
  }

  /**
   * Broadcast sync started
   */
  notifySyncStarted(): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.SYNC_STARTED);
  }

  /**
   * Broadcast sync completed
   */
  notifySyncCompleted(): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.SYNC_COMPLETED);
  }

  /**
   * Broadcast realtime connection state
   */
  notifyRealtimeState(snapshot: RealtimeConnectionSnapshot): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.REALTIME_STATE, {
      realtimeConnection: snapshot,
    });
  }

  /**
   * Broadcast a validated realtime server message
   */
  notifyRealtimeEvent(message: RealtimeServerMessage): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.REALTIME_EVENT, {
      realtimeMessage: message,
      topic: 'topic' in message ? message.topic : undefined,
      tableName: 'table' in message ? message.table : undefined,
    });
  }

  /**
   * Broadcast realtime subscription state
   */
  notifyRealtimeSubscriptionState(snapshot: RealtimeSubscriptionSnapshot): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.REALTIME_SUBSCRIPTION_STATE, {
      realtimeSubscription: snapshot,
      topic: snapshot.topic,
      tableName: snapshot.table,
    });
  }

  /**
   * Broadcast a realtime resync request
   */
  notifyRealtimeResync(topic: string, table: string, reason: string): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.REALTIME_RESYNC, {
      topic,
      tableName: table,
      reason,
    });
  }

  /**
   * Broadcast cache update
   */
  notifyCacheUpdated(tableName: string, queryKeys: QueryKeyBase[]): void {
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.CACHE_UPDATED, { tableName, queryKeys });
  }

  /**
   * Dispose implementation
   */
  protected onDispose(): void {
    this.stop();
    this.handlers.clear();
    this.logger.debug('Disposed');
  }

  /**
   * Calculate deterministic delay based on tab ID
   * Uses hashPayloadSync from foundation-utils for consistent hashing
   * Used to stagger elections and prevent conflicts
   */
  private calculateTabIdBasedDelay(baseDelay: number, range: number): number {
    // hashPayloadSync returns a hex digest, convert to number for modulo operation
    const hashValue = parseInt(hashPayloadSync(this.tabId), 16);
    return baseDelay + (hashValue % range);
  }

  /**
   * Start leader election process
   * Uses a Raft-inspired approach with term numbers to prevent split-brain
   */
  private startLeaderElection(): void {
    // Start listening for leader heartbeats
    this.startLeaderCheck();

    // Initial election delay - staggered to reduce conflicts
    // Use deterministic delay based on tab ID to ensure consistent ordering
    const delay = this.calculateTabIdBasedDelay(
      DEFAULT_INITIAL_ELECTION_BASE_DELAY_MS,
      DEFAULT_INITIAL_ELECTION_DELAY_RANGE_MS,
    );

    // Dispose any existing initial election timer
    this.initialElectionTimer?.dispose();

    this.initialElectionTimer = new SafeTimer({
      delay,
      callback: () => {
        this.initialElectionTimer = null;
        if (!this.currentLeaderId && !this.isDisposed) {
          this.initiateElection();
        }
      },
      autoStart: true,
    });
  }

  /**
   * Initiate a leader election with a new term
   */
  private initiateElection(): void {
    if (this._isLeader || this.isDisposed || this.isElectionInProgress) return;

    this.isElectionInProgress = true;

    // Increment term for this election
    this.electionTerm = Math.max(this.electionTerm, this.currentLeaderTerm) + 1;

    this.logger.debug('Initiating election for term:', this.electionTerm);

    // Broadcast candidacy with term number
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.LEADER_CANDIDATE, {
      leaderId: this.tabId,
      term: this.electionTerm,
    });

    // Dispose any existing election timer
    this.electionTimer?.dispose();

    // Wait for objections, then become leader if no higher-term candidate
    this.electionTimer = new SafeTimer({
      delay: DEFAULT_ELECTION_TIMEOUT_MS,
      callback: () => {
        this.electionTimer = null;
        if (this.isDisposed || !this.isElectionInProgress) return;

        // If we're still a candidate and no leader has been announced with higher term
        if (!this.currentLeaderId || this.electionTerm > this.currentLeaderTerm) {
          this.becomeLeader(this.electionTerm);
        }

        this.isElectionInProgress = false;
      },
      autoStart: true,
    });
  }

  /**
   * Become the leader with a specific term
   */
  private becomeLeader(term: number): void {
    if (this.isDisposed) return;

    this._isLeader = true;
    this.currentLeaderId = this.tabId;
    this.currentLeaderTerm = term;
    this.lastLeaderHeartbeat = Date.now();

    // Announce leadership with term
    this.broadcast(CROSS_TAB_MESSAGE_TYPE.LEADER_ELECTED, {
      leaderId: this.tabId,
      term: term,
    });

    // Start sending heartbeats
    this.startLeaderHeartbeat();

    this.logger.debug('Became leader for term:', term);

    // Notify handlers
    const handlers = this.handlers.get(CROSS_TAB_MESSAGE_TYPE.LEADER_ELECTED);
    if (handlers) {
      const message: CrossTabMessage = {
        type: CROSS_TAB_MESSAGE_TYPE.LEADER_ELECTED,
        tabId: this.tabId,
        timestamp: Date.now(),
        payload: { leaderId: this.tabId, term: term },
      };
      for (const handler of handlers) {
        try {
          handler(message);
        } catch (error) {
          this.logger.error('Handler error:', error);
        }
      }
    }
  }

  /**
   * Try to become the leader (deprecated - use initiateElection)
   * Kept for backward compatibility
   */
  private tryBecomeLeader(): void {
    this.initiateElection();
  }

  /**
   * Current heartbeat interval (adaptive - starts at base and increases to max).
   */
  private currentHeartbeatInterval = 0;

  /**
   * Number of consecutive heartbeats without activity (for adaptive interval).
   */
  private consecutiveQuietHeartbeats = 0;

  /**
   * Start sending leader heartbeats with adaptive interval.
   *
   * Uses exponential backoff for stable systems:
   * - Starts at base interval (default 2000ms)
   * - Increases to max interval (4x base) when no activity
   * - Resets to base interval on activity
   *
   * This reduces message overhead in stable systems while maintaining
   * responsiveness during transitions.
   */
  private startLeaderHeartbeat(): void {
    if (this.leaderHeartbeatTimer?.isActive) return;

    // Initialize adaptive interval
    this.currentHeartbeatInterval = this.config.leaderHeartbeatInterval;
    this.consecutiveQuietHeartbeats = 0;

    // Use adaptive scheduling instead of fixed interval
    this.scheduleNextHeartbeat();
  }

  /**
   * Schedule the next heartbeat with adaptive interval using SafeTimer.
   */
  private scheduleNextHeartbeat(): void {
    if (this.isDisposed || !this._isLeader) return;

    // Dispose previous timer if exists
    this.leaderHeartbeatTimer?.dispose();

    this.leaderHeartbeatTimer = new SafeTimer({
      delay: this.currentHeartbeatInterval,
      callback: () => {
        if (this._isLeader && !this.isDisposed) {
          this.broadcast(CROSS_TAB_MESSAGE_TYPE.LEADER_HEARTBEAT, {
            leaderId: this.tabId,
            term: this.currentLeaderTerm,
          });

          // Increase interval after consecutive quiet heartbeats (exponential backoff)
          this.consecutiveQuietHeartbeats++;
          if (this.consecutiveQuietHeartbeats > 3) {
            // Cap at max interval (4x base)
            const maxInterval = this.config.leaderHeartbeatInterval * 4;
            this.currentHeartbeatInterval = Math.min(
              this.currentHeartbeatInterval * 1.5,
              maxInterval,
            );
          }

          // Schedule next heartbeat
          this.scheduleNextHeartbeat();
        }
      },
      autoStart: true,
    });
  }

  /**
   * Reset heartbeat interval to base (call when activity detected).
   * This ensures responsiveness during active periods.
   */
  resetHeartbeatInterval(): void {
    this.currentHeartbeatInterval = this.config.leaderHeartbeatInterval;
    this.consecutiveQuietHeartbeats = 0;
  }

  /**
   * Stop sending leader heartbeats
   */
  private stopLeaderHeartbeat(): void {
    this.leaderHeartbeatTimer?.dispose();
    this.leaderHeartbeatTimer = null;
    this.currentHeartbeatInterval = this.config.leaderHeartbeatInterval;
    this.consecutiveQuietHeartbeats = 0;
  }

  /**
   * Start checking for leader health using ManagedInterval (idempotent cleanup registration)
   */
  private startLeaderCheck(): void {
    if (this.leaderCheckInterval?.isActive) return;

    this.leaderCheckInterval = new ManagedInterval({
      interval: this.config.leaderHeartbeatInterval,
      callback: () => {
        if (this.isDisposed) return;

        // If we're the leader, nothing to check
        if (this._isLeader) return;

        // Check if leader has timed out
        if (
          this.currentLeaderId &&
          Date.now() - this.lastLeaderHeartbeat > this.config.leaderTimeout
        ) {
          this.logger.debug('Leader timed out, starting election');
          this.currentLeaderId = null;
          this.tryBecomeLeader();
        }
      },
      autoStart: true,
    });
  }

  /**
   * Stop checking for leader health
   */
  private stopLeaderCheck(): void {
    this.leaderCheckInterval?.dispose();
    this.leaderCheckInterval = null;
  }

  /**
   * Handle incoming messages with Zod validation
   */
  private handleMessage = (event: MessageEvent<unknown>): void => {
    if (this.isDisposed) return;

    // Parse and validate with Zod schema
    const validatedMessage = parseAndValidateCrossTabMessage(event.data);

    if (!validatedMessage) {
      this.logger.warn('Received invalid cross-tab message, ignoring');
      return;
    }

    const message = validatedMessage;

    // Ignore own messages
    if (message.tabId === this.tabId) {
      return;
    }

    this.logger.debug('Received:', message.type, 'from tab:', message.tabId);

    // Handle leader election messages with term-based resolution
    switch (message.type) {
      case CROSS_TAB_MESSAGE_TYPE.LEADER_CANDIDATE: {
        // Another tab is requesting leadership
        const { term: candidateTerm } = extractLeaderPayload(message.payload);

        // If we're leader with a higher or equal term, reject by sending heartbeat
        if (this._isLeader && this.currentLeaderTerm >= candidateTerm) {
          this.broadcast(CROSS_TAB_MESSAGE_TYPE.LEADER_HEARTBEAT, {
            leaderId: this.tabId,
            term: this.currentLeaderTerm,
          });
        }
        // If candidate has higher term, update our term and clear election state
        else if (candidateTerm > this.currentLeaderTerm) {
          this.currentLeaderTerm = candidateTerm;
          if (this._isLeader) {
            this._isLeader = false;
            this.stopLeaderHeartbeat();
            this.logger.debug('Stepping down for higher term candidate:', candidateTerm);
          }
        }
        break;
      }

      case CROSS_TAB_MESSAGE_TYPE.LEADER_ELECTED: {
        // Another tab became leader
        const { leaderId: newLeaderId, term: newTerm } = extractLeaderPayload(message.payload);

        if (newLeaderId) {
          // Only accept leader with higher or equal term
          if (newTerm >= this.currentLeaderTerm) {
            // If we're also leader, the one with higher term wins
            // If terms are equal, lower tab ID wins for consistency
            if (this._isLeader) {
              if (
                newTerm > this.currentLeaderTerm ||
                (newTerm === this.currentLeaderTerm && message.tabId < this.tabId)
              ) {
                this._isLeader = false;
                this.stopLeaderHeartbeat();
                this.logger.debug('Lost leadership to:', message.tabId, 'term:', newTerm);
              } else {
                // We have equal or higher authority, reassert leadership
                this.broadcast(CROSS_TAB_MESSAGE_TYPE.LEADER_HEARTBEAT, {
                  leaderId: this.tabId,
                  term: this.currentLeaderTerm,
                });
                break;
              }
            }
            this.currentLeaderId = newLeaderId;
            this.currentLeaderTerm = newTerm;
            this.lastLeaderHeartbeat = Date.now();
            this.isElectionInProgress = false;
          }
        }
        break;
      }

      case CROSS_TAB_MESSAGE_TYPE.LEADER_HEARTBEAT: {
        const { leaderId: heartbeatLeaderId, term: heartbeatTerm } = extractLeaderPayload(
          message.payload,
        );

        // Only accept heartbeat from current leader with valid term
        if (heartbeatTerm >= this.currentLeaderTerm) {
          const previousLeaderTerm = this.currentLeaderTerm;

          this.currentLeaderId = heartbeatLeaderId ?? null;
          this.currentLeaderTerm = heartbeatTerm;
          this.lastLeaderHeartbeat = Date.now();
          this.isElectionInProgress = false;

          // Step down if we thought we were leader but someone else has equal/higher term
          if (this._isLeader && heartbeatLeaderId && heartbeatLeaderId !== this.tabId) {
            if (
              heartbeatTerm > previousLeaderTerm ||
              (heartbeatTerm === previousLeaderTerm && message.tabId < this.tabId)
            ) {
              this._isLeader = false;
              this.stopLeaderHeartbeat();
              this.logger.debug('Stepping down due to heartbeat from:', heartbeatLeaderId);
            }
          }
        }
        break;
      }

      case CROSS_TAB_MESSAGE_TYPE.LEADER_RESIGN:
        if (message.payload?.leaderId === this.currentLeaderId) {
          this.logger.debug('Leader resigned, starting election');
          this.currentLeaderId = null;
          this.isElectionInProgress = false;

          // Initiate election with staggered delay based on tab ID
          const delay = this.calculateTabIdBasedDelay(
            DEFAULT_RESIGN_ELECTION_BASE_DELAY_MS,
            DEFAULT_RESIGN_ELECTION_DELAY_RANGE_MS,
          );

          // Dispose any existing resign election timer
          this.resignElectionTimer?.dispose();

          this.resignElectionTimer = new SafeTimer({
            delay,
            callback: () => {
              this.resignElectionTimer = null;
              if (!this.currentLeaderId && !this.isDisposed) {
                this.initiateElection();
              }
            },
            autoStart: true,
          });
        }
        break;
    }

    // Call handlers
    const handlers = this.handlers.get(message.type);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(message);
        } catch (error) {
          this.logger.error('Handler error:', error);
        }
      }
    }
  };
}

/**
 * Singleton factory for cross-tab manager
 */
const crossTabManagerFactory = createSingletonFactory(
  (config: CrossTabManagerConfig | undefined) => new CrossTabManager(config),
  {
    name: 'CrossTabManager',
    onDispose: (instance) => {
      if (instance instanceof CrossTabManager) {
        instance.dispose();
      }
    },
  },
);

/**
 * Get or create cross-tab manager singleton instance.
 */
export const getCrossTabManager = (config?: CrossTabManagerConfig): CrossTabManager =>
  crossTabManagerFactory.getInstance(config);

/**
 * Reset cross-tab manager singleton (for testing).
 */
export const resetCrossTabManager = (): void => {
  void crossTabManagerFactory.reset();
};

/**
 * Create a new CrossTabManager instance (non-singleton).
 */
export const createCrossTabManager = (config?: CrossTabManagerConfig): CrossTabManager =>
  new CrossTabManager(config);
