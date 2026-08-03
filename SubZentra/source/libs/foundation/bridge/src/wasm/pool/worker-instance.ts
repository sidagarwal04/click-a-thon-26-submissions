/**
 * Worker Instance
 *
 * Wraps a single DuckDB-WASM instance with sequential query execution.
 * Each worker maintains its own query queue and executes queries one at a time.
 *
 * @module wasm/pool/worker-instance
 */

import type { AsyncDuckDB, AsyncDuckDBConnection } from '@duckdb/duckdb-wasm';

import type { QueryId, WorkerId } from '@open-zentra/foundation-data-model';
import {
  QueryCancelledError,
  QueryExecutionError,
  Timestamp,
} from '@open-zentra/foundation-data-model';
import type { Logger } from '@open-zentra/foundation-utils';
import {
  createDebugLogger,
  createDeferred,
  getErrorMessage,
  normalizeError,
  type Deferred,
} from '@open-zentra/foundation-utils';

import { convertArrowToQueryResult } from '../../duckdb/arrow-converter';
import { WorkerError, WorkerInitializationError } from '../../errors/pool-errors';
import { WORKER_STATUS } from '../../types';
import type { QueryResult, WorkerInfo, WorkerStatus } from '../../types';
import { createDuckDBInstance } from '../duckdb-init';

// =============================================================================
// Types
// =============================================================================

/**
 * Internal query queue item with deferred promise
 */
interface QueuedQuery {
  readonly queryId: QueryId;
  readonly sql: string;
  readonly deferred: Deferred<QueryResult>;
  readonly signal?: AbortSignal;
  readonly submittedAt: Timestamp;
  startedAt?: Timestamp;
  abortHandler?: () => void;
}

/**
 * Worker configuration
 */
export interface WorkerInstanceConfig {
  readonly debug?: boolean;
}

// =============================================================================
// Worker Instance Class
// =============================================================================

/**
 * Worker Instance wrapping a single DuckDB-WASM instance
 *
 * Features:
 * - Sequential query execution (one at a time)
 * - Internal queue for pending queries
 * - Cancellation support with proper cleanup
 * - Status tracking
 */
export class WorkerInstance {
  readonly id: WorkerId;

  private db: AsyncDuckDB | null = null;
  private conn: AsyncDuckDBConnection | null = null;
  private worker: Worker | null = null;

  private _status: WorkerStatus = WORKER_STATUS.INITIALIZING;
  private readonly queue: QueuedQuery[] = [];
  private currentQuery: QueuedQuery | null = null;
  private isProcessing = false;

  private totalExecuted = 0;
  private readonly createdAt: Timestamp;
  private lastActivityAt: Timestamp;
  private lastError?: string;
  private readonly logger: Logger;

  constructor(id: WorkerId, config: WorkerInstanceConfig = {}) {
    this.id = id;
    this.createdAt = Timestamp.now();
    this.lastActivityAt = Timestamp.now();
    this.logger = createDebugLogger(`Worker:${id}`, config.debug ?? false);
  }

  // ===========================================================================
  // Public Getters
  // ===========================================================================

  /**
   * Get current worker status
   */
  get status(): WorkerStatus {
    return this._status;
  }

  /**
   * Get number of queries in queue (including current)
   */
  get queueLength(): number {
    return this.queue.length + (this.currentQuery ? 1 : 0);
  }

  /**
   * Get worker info for monitoring
   */
  getInfo(): WorkerInfo {
    return {
      id: this.id,
      status: this._status,
      queueLength: this.queueLength,
      currentQueryId: this.currentQuery?.queryId ?? null,
      totalExecuted: this.totalExecuted,
      createdAt: this.createdAt,
      lastActivityAt: this.lastActivityAt,
      lastError: this.lastError,
    };
  }

  // ===========================================================================
  // Lifecycle Methods
  // ===========================================================================

  /**
   * Initialize the DuckDB instance
   *
   * @throws WorkerInitializationError if initialization fails
   */
  async initialize(): Promise<void> {
    if (this._status !== 'initializing') {
      throw new WorkerError(this.id, `Cannot initialize worker in status: ${this._status}`);
    }

    this.logger.info('Initializing worker');

    try {
      const { db, conn, worker } = await createDuckDBInstance();
      this.db = db;
      this.conn = conn;
      this.worker = worker;
      this._status = WORKER_STATUS.IDLE;
      this.lastActivityAt = Timestamp.now();
      this.logger.info('Initialized successfully');
    } catch (error) {
      this._status = WORKER_STATUS.ERROR;
      const err = normalizeError(error);
      this.lastError = err.message;
      this.logger.error('Initialization failed', { error: err.message });
      throw new WorkerInitializationError(this.id, err);
    }
  }

  /**
   * Shutdown the worker instance
   *
   * Rejects all queued queries and releases resources.
   */
  async shutdown(): Promise<void> {
    this.logger.info('Shutting down', { queueLength: this.queue.length });
    this._status = WORKER_STATUS.SHUTDOWN;

    // Reject all queued queries
    for (const queuedQuery of this.queue) {
      this.cleanupAbortHandler(queuedQuery);
      queuedQuery.deferred.reject(new QueryCancelledError(queuedQuery.queryId, 'shutdown'));
    }
    this.queue.length = 0;

    // Reject current query if any
    if (this.currentQuery) {
      this.cleanupAbortHandler(this.currentQuery);
      this.currentQuery.deferred.reject(
        new QueryCancelledError(this.currentQuery.queryId, 'shutdown'),
      );
      this.currentQuery = null;
    }

    // Close connection and terminate
    try {
      if (this.conn) {
        await this.conn.close();
        this.conn = null;
      }
      if (this.db) {
        await this.db.terminate();
        this.db = null;
      }
      if (this.worker) {
        this.worker.terminate();
        this.worker = null;
      }
    } catch (error) {
      this.logger.error('Shutdown error', {
        error: getErrorMessage(error),
      });
    }

    this.logger.info('Shutdown complete');
  }

  // ===========================================================================
  // Query Execution
  // ===========================================================================

  /**
   * Submit a query for execution
   *
   * @param queryId - Unique query identifier
   * @param sql - SQL query to execute
   * @param signal - Optional AbortSignal for cancellation
   * @returns Promise that resolves with the query result
   *
   * @throws WorkerError if worker is in invalid state
   */
  execute(queryId: QueryId, sql: string, signal?: AbortSignal): Promise<QueryResult> {
    if (this._status === WORKER_STATUS.SHUTDOWN) {
      return Promise.reject(new WorkerError(this.id, 'Worker is shut down'));
    }

    if (this._status === WORKER_STATUS.ERROR) {
      return Promise.reject(
        new WorkerError(this.id, `Worker is in error state: ${this.lastError}`),
      );
    }

    this.logger.debug('Queueing query', { queryId, sqlPreview: sql.slice(0, 50) });

    // Create deferred promise for this query
    const deferred = createDeferred<QueryResult>();

    // Create queue item
    const queuedQuery: QueuedQuery = {
      queryId,
      sql,
      deferred,
      signal,
      submittedAt: Timestamp.now(),
    };

    // Set up abort handler
    if (signal) {
      const abortHandler = () => this.handleAbort(queryId);
      signal.addEventListener('abort', abortHandler, { once: true });
      queuedQuery.abortHandler = abortHandler;
    }

    // Add to queue
    this.queue.push(queuedQuery);

    // Start processing if not already
    this.processQueue();

    return deferred.promise;
  }

  /**
   * Cancel a running or queued query
   *
   * @param queryId - Query ID to cancel
   * @returns true if query was found and will be cancelled
   */
  cancel(queryId: QueryId): boolean {
    // Try to remove from queue first
    const index = this.queue.findIndex((q) => q.queryId === queryId);
    if (index !== -1) {
      const removed = this.queue.splice(index, 1)[0];
      this.cleanupAbortHandler(removed);
      removed.deferred.reject(new QueryCancelledError(queryId, 'user'));
      this.logger.debug('Cancelled queued query', { queryId });
      return true;
    }

    // If it's the current query, mark for cancellation
    if (this.currentQuery?.queryId === queryId) {
      this.logger.debug('Query is currently running, will reject on completion', {
        queryId,
      });
      return true;
    }

    return false;
  }

  // ===========================================================================
  // Private Methods
  // ===========================================================================

  /**
   * Handle abort signal
   */
  private handleAbort(queryId: QueryId): void {
    // Remove from queue if still there
    const index = this.queue.findIndex((q) => q.queryId === queryId);
    if (index !== -1) {
      const removed = this.queue.splice(index, 1)[0];
      this.cleanupAbortHandler(removed);
      removed.deferred.reject(new QueryCancelledError(queryId, 'user'));
      this.logger.debug('Query aborted while in queue', { queryId });
    }
    // If running, it will be handled when execution completes
  }

  /**
   * Clean up abort handler for a query
   */
  private cleanupAbortHandler(query: QueuedQuery): void {
    if (query.signal && query.abortHandler) {
      query.signal.removeEventListener('abort', query.abortHandler);
      query.abortHandler = undefined;
    }
  }

  /**
   * Check if worker has transitioned to shutdown state.
   */
  private isShutdownStatus(): boolean {
    return this._status === WORKER_STATUS.SHUTDOWN;
  }

  /**
   * Process the query queue sequentially
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessing) return;
    if (this.queue.length === 0) return;
    if (this._status !== 'idle' && this._status !== 'busy') return;

    this.isProcessing = true;

    // Status can change asynchronously during loop execution
    while (this.queue.length > 0 && !this.isShutdownStatus()) {
      const queuedQuery = this.queue.shift();
      if (!queuedQuery) {
        continue;
      }
      this.currentQuery = queuedQuery;
      this._status = WORKER_STATUS.BUSY;
      this.lastActivityAt = Timestamp.now();

      try {
        await this.executeQuery(queuedQuery);
      } catch (error) {
        // Error is already handled in executeQuery
        this.logger.error('Query failed', {
          queryId: queuedQuery.queryId,
          error: getErrorMessage(error),
        });
      } finally {
        // Clean up abort handler
        this.cleanupAbortHandler(queuedQuery);
      }

      this.currentQuery = null;
      this.totalExecuted++;
    }

    this._status = this.isShutdownStatus() ? WORKER_STATUS.SHUTDOWN : WORKER_STATUS.IDLE;
    this.isProcessing = false;
    this.lastActivityAt = Timestamp.now();
  }

  /**
   * Execute a single query
   */
  private async executeQuery(queuedQuery: QueuedQuery): Promise<void> {
    const { queryId, sql, deferred, signal } = queuedQuery;
    queuedQuery.startedAt = Timestamp.now();

    this.logger.debug('Executing query', {
      queryId,
      sqlPreview: sql.slice(0, 100),
    });

    // Check if already aborted
    if (signal?.aborted) {
      deferred.reject(new QueryCancelledError(queryId, 'user'));
      return;
    }

    if (!this.conn) {
      deferred.reject(new WorkerError(this.id, 'No database connection'));
      return;
    }

    try {
      const startTime = performance.now();
      const result = await this.conn.query(sql);
      const executionTimeMs = performance.now() - startTime;

      // Check if aborted during execution
      if (signal?.aborted) {
        deferred.reject(new QueryCancelledError(queryId, 'user'));
        return;
      }

      // Convert Arrow result to QueryResult using shared utility
      const queryResult = convertArrowToQueryResult(result, executionTimeMs);

      this.logger.debug('Query completed', {
        queryId,
        executionTimeMs: executionTimeMs.toFixed(2),
        rowCount: queryResult.rows.length,
      });

      deferred.resolve(queryResult);
    } catch (error) {
      const err = normalizeError(error);
      this.logger.error('Query execution error', {
        queryId,
        error: err.message,
      });
      deferred.reject(new QueryExecutionError(queryId, sql, err));
    }
  }
}
