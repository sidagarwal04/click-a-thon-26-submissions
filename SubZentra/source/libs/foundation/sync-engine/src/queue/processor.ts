/**
 * Mutation queue processor with retry, conflict resolution, and exponential backoff
 * @module queue/processor
 */

import type {
  ConflictContext,
  ConflictResult,
  IdMapping,
  MutationQueueEntry,
  ProcessingResult,
} from '@open-zentra/foundation-data-model';
import {
  isPlainObject,
  isProvisionalId,
  MUTATION_STATUS,
  MUTATION_TYPE,
  Timestamp,
  tryToJsonSerializable,
} from '@open-zentra/foundation-data-model';
import { canProcessMutation } from '@open-zentra/foundation-database';
import {
  createDebugLogger,
  Disposable,
  getErrorMessage,
  hasCircularDependency,
  isNetworkError as isNetworkErrorUtil,
  Mutex,
  normalizeError,
  sleep,
  topologicalSort,
} from '@open-zentra/foundation-utils';

import type { ConflictResolver } from '../conflicts/resolver';
import {
  DEFAULT_AUTO_CLEANUP,
  DEFAULT_BATCH_SIZE,
  DEFAULT_DELAY_BETWEEN_MUTATIONS_MS,
} from '../core/defaults';
import type { OfflineQueueManager } from './manager';

// =============================================================================
// Local Retry Configuration
// =============================================================================

/**
 * Retry configuration for queue processing
 */
export interface QueueRetryConfig {
  /** Maximum number of retry attempts (default: 3) */
  maxAttempts: number;
  /** Initial delay between retries in ms (default: 1000) */
  initialDelayMs: number;
  /** Maximum delay between retries in ms (default: 30000) */
  maxDelayMs: number;
  /** Multiplier for delay between attempts (default: 2) */
  backoffMultiplier: number;
  /** Add random jitter to prevent thundering herd (default: true) */
  jitter: boolean;
  /** Function to determine if error is retryable */
  isRetryable?: (error: unknown) => boolean;
  /** Callback on each retry attempt */
  onRetry?: (attempt: number, error: unknown, delayMs: number) => void;
}

/** Default retry configuration for queue processing */
const DEFAULT_QUEUE_RETRY_CONFIG: Readonly<QueueRetryConfig> = Object.freeze({
  maxAttempts: 3,
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2,
  jitter: true,
  isRetryable: () => true,
});

/**
 * Calculate delay for a given attempt with exponential backoff and optional jitter
 */
const calculateBackoffDelay = (
  attempt: number,
  config: Pick<QueueRetryConfig, 'initialDelayMs' | 'maxDelayMs' | 'backoffMultiplier' | 'jitter'>,
): number => {
  const exponentialDelay = config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt);
  const cappedDelay = Math.min(exponentialDelay, config.maxDelayMs);
  if (config.jitter) {
    return Math.floor(cappedDelay + cappedDelay * 0.5 * Math.random());
  }
  return Math.floor(cappedDelay);
};

// =============================================================================
// Types
// =============================================================================

/**
 * Type guard to check if a value is a record-like payload suitable for ID resolution.
 *
 * @param value - Value to check
 * @returns True if value is a non-null object (record-like)
 */
const isRecordPayload = (value: unknown): value is Record<string, unknown> => isPlainObject(value);

/**
 * Mutation executor function type
 */
export type MutationExecutor = (mutation: MutationQueueEntry) => Promise<MutationExecutorResult>;

/**
 * Mutation executor result
 */
export interface MutationExecutorResult {
  success: boolean;
  data?: unknown;
  serverId?: string;
  serverTimestamp?: number;
  error?: string;
  /** Server version of data for conflict detection */
  serverData?: unknown;
}

/**
 * Queue processor configuration
 */
export interface QueueProcessorConfig {
  /** Queue manager instance */
  queueManager: OfflineQueueManager;
  /** Conflict resolver instance */
  conflictResolver: ConflictResolver;
  /** Mutation executor function */
  executor: MutationExecutor;
  /** Batch size for processing */
  batchSize?: number;
  /** Base delay between mutations in ms */
  baseDelayBetweenMutations?: number;
  /** Retry configuration */
  retryConfig?: Partial<QueueRetryConfig>;
  /** Callback on mutation success */
  onSuccess?: (mutation: MutationQueueEntry, result: MutationExecutorResult) => void;
  /** Callback on mutation failure */
  onFailure?: (mutation: MutationQueueEntry, error: string) => void;
  /** Callback on conflict */
  onConflict?: (mutation: MutationQueueEntry, context: ConflictContext) => void;
  /** Callback on errors (for error aggregation) */
  onError?: (error: Error, mutation?: MutationQueueEntry) => void;
  /** Enable debug logging */
  debug?: boolean;
  /** Auto-cleanup completed mutations after processing (default: true) */
  autoCleanup?: boolean;
}

/**
 * Mutation queue processor with proper disposal, retry logic, and conflict resolution
 */
export class QueueProcessor extends Disposable {
  private queueManager: OfflineQueueManager;
  private conflictResolver: ConflictResolver;
  private config: Required<
    Omit<
      QueueProcessorConfig,
      | 'queueManager'
      | 'conflictResolver'
      | 'onSuccess'
      | 'onFailure'
      | 'onConflict'
      | 'onError'
      | 'retryConfig'
    >
  >;
  private retryConfig: QueueRetryConfig;
  private callbacks: Pick<
    QueueProcessorConfig,
    'onSuccess' | 'onFailure' | 'onConflict' | 'onError'
  >;
  private isProcessing = false;
  private shouldStop = false;
  private processingMutex = new Mutex();
  private logger;

  constructor(config: QueueProcessorConfig) {
    super();
    this.queueManager = config.queueManager;
    this.conflictResolver = config.conflictResolver;
    this.config = {
      executor: config.executor,
      batchSize: config.batchSize ?? DEFAULT_BATCH_SIZE,
      baseDelayBetweenMutations:
        config.baseDelayBetweenMutations ?? DEFAULT_DELAY_BETWEEN_MUTATIONS_MS,
      debug: config.debug ?? false,
      autoCleanup: config.autoCleanup ?? DEFAULT_AUTO_CLEANUP,
    };
    this.retryConfig = {
      ...DEFAULT_QUEUE_RETRY_CONFIG,
      ...config.retryConfig,
    };
    this.callbacks = {
      onSuccess: config.onSuccess,
      onFailure: config.onFailure,
      onConflict: config.onConflict,
      onError: config.onError,
    };
    this.logger = createDebugLogger('QueueProcessor', this.config.debug);
  }

  /**
   * Check if currently processing
   */
  get processing(): boolean {
    return this.isProcessing;
  }

  /**
   * Process the mutation queue with mutex protection.
   *
   * Uses tryAcquire() pattern to avoid redundant state check inside mutex.
   * If mutex is already held, returns early with empty result.
   */
  async process(): Promise<ProcessingResult> {
    this.ensureNotDisposed();

    // Try to acquire the mutex - if already processing, return early
    const release = this.processingMutex.tryAcquire();
    if (!release) {
      this.logger.debug('Already processing, skipping');
      return { processed: 0, succeeded: 0, failed: 0, skipped: 0, idMappings: [] };
    }

    this.isProcessing = true;
    this.shouldStop = false;

    const result: ProcessingResult = {
      processed: 0,
      succeeded: 0,
      failed: 0,
      skipped: 0,
      idMappings: [],
    };

    try {
      await this.queueManager.ensureInitialized();

      // Get all pending mutations
      let pending = await this.queueManager.getPendingMutations();
      this.logger.debug('Processing', pending.length, 'pending mutations');

      const completedIds = new Set<string>();

      while (pending.length > 0 && !this.shouldStop) {
        const orderedPending = topologicalSort(
          pending,
          (mutation) => mutation.id,
          (mutation) => mutation.dependsOn ?? [],
        );
        const batch = orderedPending.slice(0, this.config.batchSize);
        let processableCount = 0;

        for (const mutation of batch) {
          if (this.shouldStop) break;

          // Check if dependencies are met
          if (!canProcessMutation(mutation, completedIds)) {
            this.logger.debug('Skipping mutation (unmet dependencies):', mutation.id);
            result.skipped++;
            continue;
          }
          processableCount++;

          // Process the mutation with retry logic
          const success = await this.processMutationWithRetry(mutation, result);

          if (success) {
            completedIds.add(mutation.id);
          }

          result.processed++;

          // Calculate delay with backoff based on retry count
          const delay = this.calculateDelay(mutation.retryCount);
          if (delay > 0) {
            await sleep(delay);
          }
        }

        // Get remaining pending mutations
        pending = await this.queueManager.getPendingMutations();
        if (!this.shouldStop && pending.length > 0 && processableCount === 0) {
          await this.failUnprocessableMutations(pending, result);
          break;
        }
      }

      this.logger.debug('Processing complete:', result);

      // Auto-cleanup completed mutations to prevent queue from growing indefinitely
      if (this.config.autoCleanup && result.succeeded > 0) {
        await this.cleanupCompleted();
      }

      return result;
    } catch (error) {
      this.logger.error('Processing error:', error);
      this.callbacks.onError?.(normalizeError(error));
      throw error;
    } finally {
      this.isProcessing = false;
      release();
    }
  }

  /**
   * Mark mutations as failed when dependency graph cannot make progress.
   */
  private async failUnprocessableMutations(
    pending: MutationQueueEntry[],
    result: ProcessingResult,
  ): Promise<void> {
    const cyclic = hasCircularDependency(
      pending,
      (mutation) => mutation.id,
      (mutation) => mutation.dependsOn ?? [],
    );

    const reason = cyclic
      ? 'Cyclic mutation dependencies detected'
      : 'Unresolvable mutation dependencies detected';

    for (const mutation of pending) {
      await this.queueManager.updateStatus(mutation.id, MUTATION_STATUS.FAILED, {
        lastError: reason,
      });
      result.failed++;
      result.processed++;
      this.callbacks.onFailure?.(mutation, reason);
    }

    this.logger.warn('Marked pending mutations as failed due to dependency deadlock', {
      count: pending.length,
      cyclic,
    });
  }

  /**
   * Clean up completed mutations from the queue
   * Called automatically after processing if autoCleanup is enabled
   */
  async cleanupCompleted(): Promise<number> {
    try {
      const deletedCount = await this.queueManager.deleteCompleted();
      if (deletedCount > 0) {
        this.logger.debug('Cleaned up', deletedCount, 'completed mutations');
      }
      return deletedCount;
    } catch (error) {
      this.logger.error('Cleanup error:', error);
      // Don't throw - cleanup failure shouldn't break the flow
      return 0;
    }
  }

  /**
   * Process a single mutation with retry logic
   */
  private async processMutationWithRetry(
    mutation: MutationQueueEntry,
    result: ProcessingResult,
  ): Promise<boolean> {
    let lastError: string | undefined;

    for (let attempt = 0; attempt < this.retryConfig.maxAttempts; attempt++) {
      if (this.shouldStop) return false;

      try {
        const success = await this.processMutation(mutation, result);
        if (success) return true;

        // If not successful but no error thrown, don't retry
        return false;
      } catch (error) {
        lastError = getErrorMessage(error);

        // Check if error is retryable
        const isRetryable = this.retryConfig.isRetryable?.(error) ?? isNetworkErrorUtil(error);

        if (!isRetryable || attempt >= this.retryConfig.maxAttempts - 1) {
          // Mark as failed
          await this.queueManager.markFailed(mutation.id, lastError);
          result.failed++;
          this.callbacks.onFailure?.(mutation, lastError);
          this.callbacks.onError?.(normalizeError(error), mutation);
          return false;
        }

        // Wait before retrying with exponential backoff
        const backoffDelay = calculateBackoffDelay(attempt, this.retryConfig);
        this.logger.debug(
          `Retry ${attempt + 1}/${this.retryConfig.maxAttempts} for mutation ${
            mutation.id
          } after ${backoffDelay}ms`,
        );
        this.retryConfig.onRetry?.(attempt + 1, error, backoffDelay);
        await sleep(backoffDelay);
      }
    }

    return false;
  }

  /**
   * Process a single mutation with conflict detection
   */
  private async processMutation(
    mutation: MutationQueueEntry,
    result: ProcessingResult,
  ): Promise<boolean> {
    this.logger.debug('Processing mutation:', mutation.id, mutation.type, mutation.tableName);

    try {
      // Mark as in progress
      await this.queueManager.markInProgress(mutation.id);

      // Resolve any provisional IDs in the payload using type guard for safety
      const resolvedPayload = isRecordPayload(mutation.payload)
        ? this.queueManager.resolvePayloadIds(mutation.payload)
        : mutation.payload;

      const resolvedMutation: MutationQueueEntry = {
        ...mutation,
        entityId: this.queueManager.resolveId(mutation.entityId),
        payload: resolvedPayload,
      };

      // Execute the mutation
      const execResult = await this.config.executor(resolvedMutation);

      if (execResult.success) {
        // Handle ID mapping for creates
        if (
          mutation.type === MUTATION_TYPE.CREATE &&
          isProvisionalId(mutation.entityId) &&
          execResult.serverId
        ) {
          const mapping: IdMapping = {
            provisionalId: mutation.entityId,
            serverId: execResult.serverId,
            tableName: mutation.tableName,
            mappedAt: new Date().toISOString(),
          };
          await this.queueManager.registerIdMapping(mapping);
          result.idMappings.push(mapping);
        }

        // Mark as completed
        await this.queueManager.markCompleted(mutation.id, execResult.serverId);

        result.succeeded++;
        this.callbacks.onSuccess?.(mutation, execResult);

        return true;
      } else {
        // Check for conflict
        if (execResult.serverData && mutation.type === MUTATION_TYPE.UPDATE) {
          const conflictResolution = this.detectAndResolveConflict(
            mutation,
            execResult.serverData,
            execResult.serverTimestamp ?? Timestamp.now(),
          );

          if (conflictResolution) {
            // Apply resolved data: re-queue the mutation with the merged/resolved payload
            const resolvedPayload = isRecordPayload(conflictResolution.resolvedData)
              ? conflictResolution.resolvedData
              : null;
            if (!resolvedPayload) {
              await this.queueManager.markFailed(
                mutation.id,
                'Conflict resolution produced non-record payload',
              );
              result.failed++;
              return false;
            }
            const serializableResolvedPayload = tryToJsonSerializable(resolvedPayload);
            if (!serializableResolvedPayload) {
              await this.queueManager.markFailed(
                mutation.id,
                'Conflict resolution produced non-serializable payload',
              );
              result.failed++;
              return false;
            }
            await this.queueManager.updateStatus(mutation.id, MUTATION_STATUS.PENDING, {
              payload: serializableResolvedPayload,
              retryCount: mutation.retryCount + 1,
              lastError: `Conflict resolved (winner: ${conflictResolution.winner})`,
            });
            // Not counted as failed — it will be retried with resolved data
            return false;
          }
        }

        // Mark as failed
        await this.queueManager.markFailed(mutation.id, execResult.error ?? 'Unknown error');

        result.failed++;
        this.callbacks.onFailure?.(mutation, execResult.error ?? 'Unknown error');

        return false;
      }
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error('Mutation error:', errorMessage);
      throw error; // Re-throw to let retry logic handle it
    }
  }

  /**
   * Detect and resolve conflicts using the conflict resolver.
   *
   * @returns The conflict resolution result if a conflict was detected, or null if no conflict.
   *          The caller is responsible for applying `resolvedData` to the mutation payload.
   */
  private detectAndResolveConflict(
    mutation: MutationQueueEntry,
    serverData: unknown,
    serverTimestamp: number,
  ): ConflictResult | null {
    const clientData = mutation.payload;
    const clientTimestamp = mutation.timestamp;

    // Check if there's actually a conflict
    const hasConflict = this.conflictResolver.hasConflict(
      serverData,
      clientData,
      serverTimestamp,
      clientTimestamp,
    );

    if (!hasConflict) {
      return null;
    }

    this.logger.debug('Conflict detected for mutation:', mutation.id);

    // Create conflict context
    const context: ConflictContext = {
      serverData,
      serverTimestamp,
      clientData,
      clientTimestamp,
      tableName: mutation.tableName,
      entityId: mutation.entityId,
      baseData: mutation.optimisticData,
    };

    // Resolve the conflict
    const resolution = this.conflictResolver.resolve(context);

    this.logger.debug('Conflict resolved:', {
      winner: resolution.winner,
      requiresReview: resolution.requiresReview,
      conflictedFields: resolution.conflictedFields,
    });

    // Notify callback
    this.callbacks.onConflict?.(mutation, context);

    return resolution;
  }

  /**
   * Calculate delay based on retry count
   */
  private calculateDelay(retryCount: number): number {
    if (retryCount === 0) {
      return this.config.baseDelayBetweenMutations;
    }

    // Use exponential backoff for retried mutations
    return calculateBackoffDelay(retryCount - 1, {
      initialDelayMs: this.config.baseDelayBetweenMutations,
      maxDelayMs: this.retryConfig.maxDelayMs,
      backoffMultiplier: this.retryConfig.backoffMultiplier,
      jitter: this.retryConfig.jitter,
    });
  }

  /**
   * Stop processing
   */
  stop(): void {
    this.shouldStop = true;
    this.logger.debug('Stop requested');
  }

  /**
   * Dispose implementation
   */
  protected onDispose(): void {
    this.stop();
    this.logger.debug('Disposed');
  }
}

/**
 * Create a queue processor
 */
export const createQueueProcessor = (config: QueueProcessorConfig): QueueProcessor =>
  new QueueProcessor(config);
