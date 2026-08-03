/**
 * Offline mutation queue manager
 * @module queue/manager
 */

import {
  generateProvisionalId,
  isProvisionalId,
  MUTATION_STATUS,
  MUTATION_TYPE,
  SYNC_STATE_KEY,
  type CreateMutationOptions,
  type IdMapping,
  type MutationQueueEntry,
  type MutationStatus,
  type QueueStats,
} from '@open-zentra/foundation-data-model';
import type { InsightsDatabase } from '@open-zentra/foundation-database';
import { createMutationEntry, getDatabase } from '@open-zentra/foundation-database';
import {
  createDebugLogger,
  createSingletonFactory,
  Disposable,
  normalizeError,
} from '@open-zentra/foundation-utils';

import {
  DEFAULT_ID_MAPPING_TTL_MS,
  DEFAULT_MAX_ID_MAPPINGS,
  DEFAULT_MAX_RETRIES,
} from '../core/defaults';
import type { IQueueManager } from '../core/interfaces';
import { resolvePayloadProvisionalIds } from '../core/payload-id-resolution';

/**
 * Extended mutation options with optional idempotency key for deduplication.
 */
interface ExtendedCreateMutationOptions extends CreateMutationOptions {
  readonly idempotencyKey?: string;
}

/**
 * Queue manager configuration
 */
export interface QueueManagerConfig {
  /** Database instance */
  database?: InsightsDatabase;
  /** Maximum retry attempts */
  maxRetries?: number;
  /** Maximum number of ID mappings to keep (LRU eviction when exceeded) */
  maxIdMappings?: number;
  /** TTL for ID mappings in milliseconds (default: 24 hours) */
  idMappingTtlMs?: number;
  /** Enable debug logging */
  debug?: boolean;
  /** Error callback for centralized error handling */
  onError?: (error: Error, context?: string) => void;
}

/**
 * Default queue manager configuration
 */
const DEFAULT_CONFIG: Required<Omit<QueueManagerConfig, 'database' | 'onError'>> = {
  maxRetries: DEFAULT_MAX_RETRIES,
  maxIdMappings: DEFAULT_MAX_ID_MAPPINGS,
  idMappingTtlMs: DEFAULT_ID_MAPPING_TTL_MS,
  debug: false,
};

/**
 * ID Mapping store key in syncState.
 */
const ID_MAPPINGS_KEY = SYNC_STATE_KEY.ID_MAPPINGS;

/**
 * Type guard to validate IdMapping structure
 */
const isValidIdMapping = (value: unknown): value is IdMapping =>
  value !== null &&
  typeof value === 'object' &&
  'provisionalId' in value &&
  typeof value.provisionalId === 'string' &&
  'serverId' in value &&
  typeof value.serverId === 'string' &&
  'tableName' in value &&
  typeof value.tableName === 'string' &&
  'mappedAt' in value &&
  typeof value.mappedAt === 'string';

/**
 * Type guard to validate an array of IdMappings
 */
const isValidIdMappingArray = (value: unknown): value is IdMapping[] =>
  Array.isArray(value) && value.every(isValidIdMapping);

/**
 * Offline mutation queue manager with proper disposal and persistence
 */
export class OfflineQueueManager extends Disposable implements IQueueManager {
  private db: InsightsDatabase;
  private config: Required<Omit<QueueManagerConfig, 'database' | 'onError'>>;
  private onError?: (error: Error, context?: string) => void;
  private idMappings: Map<string, IdMapping> = new Map();
  private logger;
  private initialized = false;
  private initializationPromise: Promise<void> | null = null;

  constructor(config: QueueManagerConfig = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.onError = config.onError;
    this.db = config.database ?? getDatabase();
    this.logger = createDebugLogger('OfflineQueueManager', this.config.debug);
  }

  /**
   * Handle errors with optional callback
   */
  private handleError(error: unknown, context?: string): void {
    const err = normalizeError(error);
    this.logger.error(`Error in ${context ?? 'unknown'}:`, err);
    this.onError?.(err, context);
  }

  /**
   * Ensure persisted ID mappings are loaded.
   */
  ensureInitialized = async (): Promise<void> => {
    await this.initialize();
  };

  /**
   * Initialize - load persisted ID mappings with type validation
   * Uses promise-based guard to prevent race conditions from concurrent calls
   */
  private async initialize(): Promise<void> {
    // Already initialized
    if (this.initialized) return;

    // Already initializing - wait for the existing promise
    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    // Create and store the initialization promise
    this.initializationPromise = this.doInitialize();

    try {
      await this.initializationPromise;
    } finally {
      this.initializationPromise = null;
    }
  }

  /**
   * Internal initialization logic
   */
  private async doInitialize(): Promise<void> {
    try {
      const entry = await this.db.syncState.get(ID_MAPPINGS_KEY);
      if (entry?.value) {
        // Validate the retrieved data before using it
        if (isValidIdMappingArray(entry.value)) {
          for (const mapping of entry.value) {
            this.idMappings.set(mapping.provisionalId, mapping);
          }
          this.logger.debug('Loaded', this.idMappings.size, 'ID mappings from storage');

          // Clean up stale mappings from previous sessions
          this.cleanupIdMappings();
        } else {
          this.logger.warn('Invalid ID mappings format in storage, clearing');
          // Clear invalid data
          await this.db.syncState.delete(ID_MAPPINGS_KEY);
        }
      }
    } catch (error) {
      this.handleError(error, 'ID mappings initialization');
    }

    this.initialized = true;
  }

  /**
   * Persist ID mappings to database
   */
  private async persistIdMappings(): Promise<void> {
    try {
      await this.db.syncState.put({
        key: ID_MAPPINGS_KEY,
        value: Array.from(this.idMappings.values(), (mapping) => ({
          provisionalId: mapping.provisionalId,
          serverId: mapping.serverId,
          tableName: mapping.tableName,
          mappedAt: mapping.mappedAt,
        })),
        updatedAt: Date.now(),
      });
    } catch (error) {
      this.handleError(error, 'ID mappings persistence');
    }
  }

  /**
   * Generate a mutation ID
   */
  private generateMutationId(): string {
    return crypto.randomUUID();
  }

  /**
   * Add a mutation to the queue with deduplication
   * @param options - Mutation options, can include idempotencyKey for deduplication
   */
  async enqueue(
    options: CreateMutationOptions | ExtendedCreateMutationOptions,
  ): Promise<MutationQueueEntry> {
    this.ensureNotDisposed();
    await this.ensureInitialized();

    // Type-safe access to idempotency key
    if ('idempotencyKey' in options && typeof options.idempotencyKey === 'string') {
      const existing = await this.findByIdempotencyKey(options.idempotencyKey);
      if (existing) {
        this.logger.debug('Duplicate mutation found:', existing.id);
        return existing;
      }
    }

    // For creates, generate provisional ID if not provided
    let entityId = options.entityId;
    if (options.type === MUTATION_TYPE.CREATE && !entityId) {
      entityId = generateProvisionalId();
    }

    const entry = createMutationEntry(this.generateMutationId(), {
      ...options,
      entityId,
    });

    await this.db.mutations.add(entry);
    this.logger.debug('Enqueued mutation:', entry.id, entry.type, entry.tableName);

    return entry;
  }

  /**
   * Get mutation by ID
   */
  async get(id: string): Promise<MutationQueueEntry | undefined> {
    this.ensureNotDisposed();
    return this.db.mutations.get(id);
  }

  /**
   * Get all pending mutations in queue order
   */
  async getPendingMutations(): Promise<MutationQueueEntry[]> {
    this.ensureNotDisposed();
    return this.db.mutations
      .where('status')
      .anyOf([MUTATION_STATUS.PENDING, MUTATION_STATUS.OFFLINE_QUEUED])
      .sortBy('timestamp');
  }

  /**
   * Get mutations by status
   */
  async getByStatus(status: MutationStatus): Promise<MutationQueueEntry[]> {
    this.ensureNotDisposed();
    return this.db.mutations.where('status').equals(status).sortBy('timestamp');
  }

  /**
   * Update mutation status
   */
  async updateStatus(
    id: string,
    status: MutationStatus,
    updates?: Partial<MutationQueueEntry>,
  ): Promise<void> {
    this.ensureNotDisposed();
    await this.db.mutations.update(id, {
      status,
      ...updates,
    });
    this.logger.debug('Updated mutation status:', id, status);
  }

  /**
   * Mark mutation as in progress
   */
  async markInProgress(id: string): Promise<void> {
    await this.updateStatus(id, MUTATION_STATUS.IN_PROGRESS);
  }

  /**
   * Mark mutation as completed
   */
  async markCompleted(id: string, serverId?: string): Promise<void> {
    await this.updateStatus(id, MUTATION_STATUS.COMPLETED, { serverId });
  }

  /**
   * Mark mutation as failed
   */
  async markFailed(id: string, error: string): Promise<void> {
    const mutation = await this.get(id);
    if (!mutation) return;

    const newRetryCount = mutation.retryCount + 1;
    const newStatus: MutationStatus =
      newRetryCount >= this.config.maxRetries ? MUTATION_STATUS.FAILED : MUTATION_STATUS.PENDING;

    await this.updateStatus(id, newStatus, {
      retryCount: newRetryCount,
      lastError: error,
    });
  }

  /**
   * Mark all pending as offline queued.
   *
   * Uses a single modify() call which returns the count directly,
   * avoiding the redundant toArray() query.
   */
  async markAllOfflineQueued(): Promise<number> {
    this.ensureNotDisposed();

    // Dexie's modify() returns the count of modified records directly
    const count = await this.db.mutations
      .where('status')
      .equals(MUTATION_STATUS.PENDING)
      .modify({ status: MUTATION_STATUS.OFFLINE_QUEUED });

    if (count > 0) {
      this.logger.debug('Marked', count, 'mutations as offline_queued');
    }
    return count;
  }

  /**
   * Mark all offline queued as pending.
   *
   * Uses a single modify() call which returns the count directly,
   * avoiding the redundant toArray() query.
   */
  async markAllPending(): Promise<number> {
    this.ensureNotDisposed();

    // Dexie's modify() returns the count of modified records directly
    const count = await this.db.mutations
      .where('status')
      .equals(MUTATION_STATUS.OFFLINE_QUEUED)
      .modify({ status: MUTATION_STATUS.PENDING });

    if (count > 0) {
      this.logger.debug('Marked', count, 'mutations as pending');
    }
    return count;
  }

  /**
   * Delete a mutation
   */
  async delete(id: string): Promise<void> {
    this.ensureNotDisposed();
    await this.db.mutations.delete(id);
    this.logger.debug('Deleted mutation:', id);
  }

  /**
   * Delete all completed mutations
   */
  async deleteCompleted(): Promise<number> {
    this.ensureNotDisposed();
    const count = await this.db.mutations
      .where('status')
      .equals(MUTATION_STATUS.COMPLETED)
      .delete();
    this.logger.debug('Deleted', count, 'completed mutations');
    return count;
  }

  /**
   * Clear all mutations
   */
  async clear(): Promise<void> {
    this.ensureNotDisposed();
    await this.db.mutations.clear();
    this.idMappings.clear();
    await this.persistIdMappings();
    this.logger.debug('Cleared all mutations');
  }

  /**
   * Get queue statistics using efficient database-level count queries.
   *
   * Uses indexed lookups instead of loading all mutations into memory,
   * making it performant for large queues.
   */
  async getStats(): Promise<QueueStats> {
    this.ensureNotDisposed();

    // Run count queries in parallel for better performance
    const [pending, inProgress, failed, offlineQueued, total] = await Promise.all([
      this.db.mutations.where('status').equals(MUTATION_STATUS.PENDING).count(),
      this.db.mutations.where('status').equals(MUTATION_STATUS.IN_PROGRESS).count(),
      this.db.mutations.where('status').equals(MUTATION_STATUS.FAILED).count(),
      this.db.mutations.where('status').equals(MUTATION_STATUS.OFFLINE_QUEUED).count(),
      this.db.mutations.count(),
    ]);

    return {
      pending,
      inProgress,
      failed,
      offlineQueued,
      total,
    };
  }

  /**
   * Check if there are pending mutations
   */
  async hasPending(): Promise<boolean> {
    this.ensureNotDisposed();
    const count = await this.db.mutations
      .where('status')
      .anyOf([MUTATION_STATUS.PENDING, MUTATION_STATUS.OFFLINE_QUEUED])
      .count();
    return count > 0;
  }

  /**
   * Find mutation by idempotency key
   */
  async findByIdempotencyKey(key: string): Promise<MutationQueueEntry | undefined> {
    this.ensureNotDisposed();
    return this.db.mutations.where('idempotencyKey').equals(key).first();
  }

  /**
   * Register ID mapping (provisional ID -> server ID) with persistence.
   *
   * Persists synchronously to prevent data loss on crash.
   * The mapping is stored in both memory and IndexedDB atomically.
   * Automatically cleans up old mappings if the cache exceeds maxIdMappings.
   *
   * @param mapping - The ID mapping to register
   * @returns Promise that resolves when mapping is persisted
   */
  async registerIdMapping(mapping: IdMapping): Promise<void> {
    this.ensureNotDisposed();
    await this.ensureInitialized();

    // Validate the mapping before storing
    if (!isValidIdMapping(mapping)) {
      const err = new Error('Invalid IdMapping structure provided');
      this.handleError(err, 'registerIdMapping validation');
      throw err;
    }

    // Store in memory
    this.idMappings.set(mapping.provisionalId, mapping);
    this.logger.debug('Registered ID mapping:', mapping.provisionalId, '->', mapping.serverId);

    // Clean up if we're over the limit (LRU/TTL eviction)
    if (this.idMappings.size > this.config.maxIdMappings) {
      this.cleanupIdMappings();
    }

    // Persist synchronously to prevent data loss on crash
    try {
      await this.persistIdMappings();
    } catch (error) {
      // Rollback memory state on persistence failure
      this.idMappings.delete(mapping.provisionalId);
      this.handleError(error, 'ID mapping persistence after registration');
      throw error;
    }
  }

  /**
   * Get server ID for a provisional ID
   */
  getServerId(provisionalId: string): string | undefined {
    return this.idMappings.get(provisionalId)?.serverId;
  }

  /**
   * Resolve ID (returns server ID if mapped, otherwise returns original)
   */
  resolveId(id: string): string {
    if (isProvisionalId(id)) {
      return this.getServerId(id) ?? id;
    }
    return id;
  }

  /**
   * Get all ID mappings
   */
  getIdMappings(): IdMapping[] {
    return Array.from(this.idMappings.values());
  }

  /**
   * Clean up expired or excess ID mappings to prevent unbounded memory growth.
   *
   * Implements both TTL-based and LRU-based eviction:
   * - Removes mappings older than idMappingTtlMs
   * - If still over maxIdMappings, removes oldest until under limit
   *
   * Performance optimization: Pre-computes all timestamps in a single pass
   * instead of calling new Date() repeatedly during sorting.
   *
   * @returns Number of mappings removed
   */
  cleanupIdMappings(): number {
    const now = Date.now();
    const ttlMs = this.config.idMappingTtlMs;
    const maxMappings = this.config.maxIdMappings;
    let removedCount = 0;

    // Pre-compute timestamps for all mappings in a single pass
    // This avoids repeated Date parsing during TTL check and sorting
    const mappingsWithTimestamp: Array<{
      provisionalId: string;
      mappedAtMs: number;
    }> = [];

    for (const [provisionalId, mapping] of this.idMappings.entries()) {
      const mappedAtMs = new Date(mapping.mappedAt).getTime();
      mappingsWithTimestamp.push({ provisionalId, mappedAtMs });
    }

    // First pass: Remove expired mappings (TTL-based)
    for (const { provisionalId, mappedAtMs } of mappingsWithTimestamp) {
      if (now - mappedAtMs > ttlMs) {
        this.idMappings.delete(provisionalId);
        removedCount++;
      }
    }

    // Second pass: LRU eviction if still over limit
    if (this.idMappings.size > maxMappings) {
      // Filter out already-deleted entries and sort by timestamp (oldest first)
      const remaining = mappingsWithTimestamp
        .filter(({ provisionalId }) => this.idMappings.has(provisionalId))
        .sort((a, b) => a.mappedAtMs - b.mappedAtMs);

      // Remove oldest until under limit
      const toRemove = this.idMappings.size - maxMappings;
      for (let i = 0; i < toRemove && i < remaining.length; i++) {
        this.idMappings.delete(remaining[i].provisionalId);
        removedCount++;
      }
    }

    if (removedCount > 0) {
      this.logger.debug('Cleaned up', removedCount, 'old ID mappings');
      // Persist the cleaned up state
      this.persistIdMappings().catch((error) => {
        this.handleError(error, 'ID mappings cleanup persistence');
      });
    }

    return removedCount;
  }

  /**
   * Clear ID mappings with persistence
   */
  clearIdMappings(): void {
    this.idMappings.clear();
    this.persistIdMappings().catch((error) => {
      this.handleError(error, 'ID mappings clear persistence');
    });
  }

  /**
   * Update references to provisional IDs in a mutation payload
   */
  resolvePayloadIds<T extends Record<string, unknown>>(payload: T): T {
    return resolvePayloadProvisionalIds(payload, (provisionalId) =>
      this.getServerId(provisionalId),
    );
  }

  /**
   * Dispose implementation
   */
  protected onDispose(): void {
    this.idMappings.clear();
    this.logger.debug('Disposed');
  }
}

/**
 * Singleton factory for queue manager
 */
const queueManagerFactory = createSingletonFactory(
  (config: QueueManagerConfig | undefined) => new OfflineQueueManager(config),
  {
    name: 'OfflineQueueManager',
    onDispose: (instance) => {
      if (instance instanceof OfflineQueueManager) {
        instance.dispose();
      }
    },
  },
);

/**
 * Get or create queue manager singleton instance.
 */
export const getQueueManager = (config?: QueueManagerConfig): OfflineQueueManager =>
  queueManagerFactory.getInstance(config);

/**
 * Reset queue manager singleton (for testing).
 */
export const resetQueueManager = (): void => {
  void queueManagerFactory.reset();
};

/**
 * Check if queue manager instance exists.
 */
export const hasQueueManager = (): boolean => queueManagerFactory.hasInstance();

/**
 * Create a new OfflineQueueManager instance (non-singleton).
 */
export const createQueueManager = (config?: QueueManagerConfig): OfflineQueueManager =>
  new OfflineQueueManager(config);
