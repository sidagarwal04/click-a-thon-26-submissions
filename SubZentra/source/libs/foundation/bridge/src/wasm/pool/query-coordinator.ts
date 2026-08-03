/**
 * Query Coordinator
 *
 * Central orchestrator for the DuckDB worker pool that:
 * - Accepts queries with metadata (tables, priority, timeout)
 * - Acquires table locks before execution
 * - Routes to least-busy worker
 * - Manages cancellation and timeouts
 * - Handles overflow queue
 *
 * @module wasm/pool/query-coordinator
 */

import {
  QueryCancelledError,
  QueryId,
  QueryTimeoutError,
  Timestamp,
} from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  createDeferred,
  getErrorMessage,
  normalizeError,
  type Logger,
} from '@open-zentra/foundation-utils';

import { PRIORITY, QUERY_MODE } from '../../constants';
import { PoolCapacityError, PoolShutdownError } from '../../errors/pool-errors';
import type {
  DuckDBPoolConfig,
  PoolQueryResult,
  PoolStatus,
  QueryItem,
  QueryRequest,
  ResolvedPoolConfig,
} from '../../types';
import { resolvePoolConfig } from '../../utils/validation';
import { PriorityQueue } from './priority-queue';
import { TableLockManager } from './table-lock-manager';
import type { WorkerInstance } from './worker-instance';
import { WorkerPoolManager } from './worker-pool';

// =============================================================================
// Types
// =============================================================================

/**
 * Internal tracking info for active queries
 */
interface ActiveQuery {
  readonly reject: (error: Error) => void;
  readonly signal?: AbortSignal;
  readonly timeoutHandle?: ReturnType<typeof setTimeout>;
  readonly abortHandler?: () => void;
}

// =============================================================================
// Query Coordinator Class
// =============================================================================

/**
 * Query Coordinator
 *
 * Main entry point for executing queries against the DuckDB worker pool.
 */
export class QueryCoordinator {
  private readonly config: ResolvedPoolConfig;
  private readonly pool: WorkerPoolManager;
  private readonly lockManager: TableLockManager;
  private readonly overflowQueue: PriorityQueue<QueryItem>;
  private readonly logger: Logger;

  private initialized = false;
  private shuttingDown = false;
  private readonly createdAt: Timestamp;
  private totalExecuted = 0;

  /** Track active queries for cancellation and cleanup */
  private readonly activeQueries = new Map<QueryId, ActiveQuery>();

  constructor(config: DuckDBPoolConfig = {}) {
    this.config = resolvePoolConfig(config);
    this.pool = new WorkerPoolManager(this.config);
    this.lockManager = new TableLockManager({ debug: this.config.debug });
    this.overflowQueue = new PriorityQueue();
    this.createdAt = Timestamp.now();

    this.logger = createDebugLogger('QueryCoordinator', this.config.debug);
  }

  // ===========================================================================
  // Lifecycle Methods
  // ===========================================================================

  /**
   * Initialize the coordinator and worker pool
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    this.logger.info('Initializing coordinator');
    await this.pool.initialize();
    this.initialized = true;
    this.logger.info('Coordinator initialized');
  }

  /**
   * Check if coordinator is ready
   */
  isReady(): boolean {
    return this.initialized && !this.shuttingDown;
  }

  /**
   * Shutdown the coordinator and all workers
   */
  async shutdown(): Promise<void> {
    if (this.shuttingDown) return;

    this.logger.info('Shutting down coordinator', {
      activeQueries: this.activeQueries.size,
      overflowQueue: this.overflowQueue.size(),
    });

    this.shuttingDown = true;

    // Reject all active queries
    for (const [queryId, activeQuery] of this.activeQueries) {
      this.cleanupActiveQuery(queryId);
      activeQuery.reject(new PoolShutdownError(this.activeQueries.size));
    }
    this.activeQueries.clear();

    // Clear overflow queue
    const overflowItems = this.overflowQueue.clear();
    for (const item of overflowItems) {
      item.reject(new PoolShutdownError());
    }

    // Clear locks
    this.lockManager.clearAll();

    // Shutdown pool
    await this.pool.shutdown();

    this.initialized = false;
    this.logger.info('Coordinator shutdown complete');
  }

  // ===========================================================================
  // Query Execution
  // ===========================================================================

  /**
   * Execute a query
   *
   * @param request - Query request with SQL, tables, priority, etc.
   * @returns Promise resolving to query result
   */
  async query<T extends Record<string, unknown> = Record<string, unknown>>(
    request: Omit<QueryRequest, 'id'> & { id?: QueryId },
  ): Promise<PoolQueryResult<T>> {
    // Auto-initialize if needed
    if (!this.initialized) {
      await this.initialize();
    }

    if (this.shuttingDown) {
      throw new PoolShutdownError();
    }

    // Check active queries limit to prevent unbounded memory growth
    if (this.activeQueries.size >= this.config.maxActiveQueries) {
      this.logger.warn('Pool at capacity', {
        maxActiveQueries: this.config.maxActiveQueries,
        currentActive: this.activeQueries.size,
      });
      throw new PoolCapacityError(this.config.maxActiveQueries, this.activeQueries.size);
    }

    // Generate query ID
    const queryId = request.id ?? QueryId.create();
    const submittedAt = Timestamp.now();

    this.logger.debug('Query submitted', {
      queryId,
      sqlPreview: request.sql.slice(0, 80),
      priority: request.priority ?? PRIORITY.NORMAL,
    });

    // Check if already aborted
    if (request.signal?.aborted) {
      throw new QueryCancelledError(queryId, 'user');
    }

    // Create deferred promise for this query
    const deferred = createDeferred<PoolQueryResult<T>>();

    // Create query item
    const queryItem: QueryItem = {
      id: queryId,
      request: { ...request, id: queryId },
      submittedAt,
      resolve: (result) => {
        this.cleanupActiveQuery(queryId);
        deferred.resolve(result as PoolQueryResult<T>);
      },
      reject: (error) => {
        this.cleanupActiveQuery(queryId);
        deferred.reject(error);
      },
    };

    // Set up abort handler
    let abortHandler: (() => void) | undefined;
    if (request.signal) {
      abortHandler = () => this.cancelQuery(queryId);
      request.signal.addEventListener('abort', abortHandler, { once: true });
    }

    // Set up timeout
    const timeoutMs = request.timeoutMs ?? this.config.defaultQueryTimeout;
    let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
    if (timeoutMs > 0) {
      timeoutHandle = setTimeout(() => {
        this.logger.debug('Query timed out', { queryId, timeoutMs });
        this.cancelQuery(queryId);
        deferred.reject(new QueryTimeoutError(queryId, timeoutMs, request.sql));
      }, timeoutMs);
    }

    // Track active query
    const activeQuery: ActiveQuery = {
      reject: deferred.reject,
      signal: request.signal,
      timeoutHandle,
      abortHandler,
    };
    this.activeQueries.set(queryId, activeQuery);

    // Start execution (don't await - let it run)
    this.executeQuery(queryItem);

    return deferred.promise;
  }

  /**
   * Execute a query through the pool
   */
  private async executeQuery(queryItem: QueryItem): Promise<void> {
    const { id, request } = queryItem;
    const priority = request.priority ?? PRIORITY.NORMAL;

    try {
      // Try to get a worker
      const worker = this.pool.getLeastBusyWorker();

      if (!worker) {
        // Check overflow queue backpressure
        if (this.overflowQueue.size() >= this.config.maxOverflowQueueSize) {
          this.logger.warn('Overflow queue at capacity', {
            queryId: id,
            maxOverflowQueueSize: this.config.maxOverflowQueueSize,
            currentSize: this.overflowQueue.size(),
          });
          throw new PoolCapacityError(this.config.maxOverflowQueueSize, this.overflowQueue.size());
        }

        // All workers at capacity, add to overflow queue
        this.logger.debug('Adding to overflow queue', { queryId: id });
        this.overflowQueue.enqueue(queryItem, priority);
        // Query will be picked up by processOverflowQueue when a worker is free
        return;
      }

      await this.executeQueryOnWorkerWithLocks(queryItem, worker);
    } catch (error) {
      this.logger.error('Query execution failed', {
        queryId: id,
        error: getErrorMessage(error),
      });
      queryItem.reject(normalizeError(error));
    } finally {
      // Process overflow queue
      this.processOverflowQueue();
    }
  }

  /**
   * Execute a query on a worker with table lock coordination.
   *
   * Lock acquisition happens right before dispatch to the worker so queued
   * overflow queries do not hold locks while waiting for capacity.
   */
  private async executeQueryOnWorkerWithLocks(
    queryItem: QueryItem,
    worker: WorkerInstance,
  ): Promise<void> {
    const tables = queryItem.request.tables ?? [];
    const mode = queryItem.request.mode ?? QUERY_MODE.READ;
    let locksAcquired = false;

    try {
      if (this.config.enableTableLocking && tables.length > 0) {
        this.logger.debug('Acquiring locks', { queryId: queryItem.id, tables, mode });
        await this.lockManager.acquireLocks(tables, mode);
        locksAcquired = true;
        this.logger.debug('Locks acquired', { queryId: queryItem.id });
      }

      if (queryItem.request.signal?.aborted) {
        throw new QueryCancelledError(queryItem.id, 'user');
      }

      await this.executeQueryOnWorker(queryItem, worker);
    } finally {
      if (locksAcquired) {
        this.lockManager.releaseLocks(tables, mode);
        this.logger.debug('Locks released', { queryId: queryItem.id });
      }
    }
  }

  /**
   * Execute a query on a specific worker
   */
  private async executeQueryOnWorker(queryItem: QueryItem, worker: WorkerInstance): Promise<void> {
    const { id, request, submittedAt } = queryItem;

    this.logger.debug('Routing to worker', { queryId: id, workerId: worker.id });

    try {
      // Check if cancelled
      if (request.signal?.aborted) {
        throw new QueryCancelledError(id, 'user');
      }

      const startTime = Timestamp.now();

      // Execute on worker - pass the query details directly
      const result = await worker.execute(id, request.sql, request.signal);

      const queueTimeMs = startTime - submittedAt;
      const totalTimeMs = Timestamp.now() - submittedAt;

      // Build result with metadata
      const poolResult: PoolQueryResult = {
        ...result,
        queryId: id,
        workerId: worker.id,
        queueTimeMs,
        totalTimeMs,
      };

      this.totalExecuted++;
      this.logger.debug('Query completed', {
        queryId: id,
        totalTimeMs,
        queueTimeMs,
      });

      queryItem.resolve(poolResult);
    } catch (error) {
      queryItem.reject(normalizeError(error));
    }
  }

  /** Flag to prevent concurrent overflow processing */
  private isProcessingOverflow = false;

  /** Maximum queries to dispatch per processing tick */
  private static readonly MAX_BATCH_SIZE = 10;

  /**
   * Process queries from the overflow queue
   *
   * Uses iterative processing with batch limits to avoid deep call stacks.
   * Schedules continuation via microtask only after processing a batch.
   */
  private processOverflowQueue(): void {
    // Prevent concurrent processing
    if (this.isProcessingOverflow) return;
    if (this.overflowQueue.isEmpty() || this.shuttingDown) return;

    this.isProcessingOverflow = true;

    try {
      // Process up to MAX_BATCH_SIZE queries in this tick
      let dispatched = 0;

      while (dispatched < QueryCoordinator.MAX_BATCH_SIZE && !this.shuttingDown) {
        // Check if queue is empty
        if (this.overflowQueue.isEmpty()) break;

        // Get available worker
        const worker = this.pool.getLeastBusyWorker();
        if (!worker) {
          // No workers available, will be triggered again when a query completes
          break;
        }

        const queryItem = this.overflowQueue.dequeue();
        if (!queryItem) break;

        this.logger.debug('Processing overflow query', {
          queryId: queryItem.id,
          workerId: worker.id,
        });

        // Execute the query (async, don't await)
        this.executeQueryOnWorkerWithLocks(queryItem, worker).finally(() => {
          // Schedule next processing when this query completes
          queueMicrotask(() => this.processOverflowQueue());
        });

        dispatched++;
      }

      // If there are more items and we have workers, schedule continuation
      if (!this.overflowQueue.isEmpty() && !this.shuttingDown) {
        queueMicrotask(() => this.processOverflowQueue());
      }
    } finally {
      this.isProcessingOverflow = false;
    }
  }

  // ===========================================================================
  // Cancellation
  // ===========================================================================

  /**
   * Cancel a query
   */
  cancelQuery(queryId: QueryId | string): boolean {
    const normalizedQueryId = typeof queryId === 'string' ? QueryId.from(queryId) : queryId;
    const activeQuery = this.activeQueries.get(normalizedQueryId);
    if (!activeQuery) {
      return false;
    }

    this.logger.debug('Cancelling query', { queryId: normalizedQueryId });

    // Clean up (clears timeout and abort handler)
    this.cleanupActiveQuery(normalizedQueryId);

    // Try to remove from overflow queue
    const removed = this.overflowQueue.remove((q) => q.id === normalizedQueryId);
    if (removed) {
      this.logger.debug('Query removed from overflow queue', { queryId: normalizedQueryId });
      activeQuery.reject(new QueryCancelledError(normalizedQueryId, 'user'));
      return true;
    }

    // Try to cancel on workers
    for (const workerId of this.pool.getWorkerIds()) {
      const worker = this.pool.getWorker(workerId);
      if (worker?.cancel(normalizedQueryId)) {
        this.logger.debug('Query cancelled on worker', { queryId: normalizedQueryId, workerId });
        return true;
      }
    }

    return false;
  }

  /**
   * Clean up after query completion
   */
  private cleanupActiveQuery(queryId: QueryId): void {
    const activeQuery = this.activeQueries.get(queryId);
    if (!activeQuery) return;

    // Clear timeout
    if (activeQuery.timeoutHandle) {
      clearTimeout(activeQuery.timeoutHandle);
    }

    // Remove abort handler
    if (activeQuery.abortHandler && activeQuery.signal) {
      activeQuery.signal.removeEventListener('abort', activeQuery.abortHandler);
    }

    this.activeQueries.delete(queryId);
  }

  // ===========================================================================
  // Status & Configuration
  // ===========================================================================

  /**
   * Get pool status
   */
  getStatus(): PoolStatus {
    const workers = this.pool.getWorkerStatus();
    const totalPending =
      workers.reduce((sum, w) => sum + w.queueLength, 0) + this.overflowQueue.size();

    return {
      ready: this.isReady(),
      shuttingDown: this.shuttingDown,
      workers,
      globalQueueLength: this.overflowQueue.size(),
      totalExecuted: this.totalExecuted,
      totalPending,
      uptimeMs: Timestamp.now() - this.createdAt,
    };
  }

  /**
   * Get configuration
   */
  getConfig(): ResolvedPoolConfig {
    return { ...this.config };
  }
}
