/**
 * Worker Pool Manager
 *
 * Manages a pool of DuckDB worker instances with:
 * - Configurable number of workers
 * - Least-busy worker routing
 * - Worker lifecycle management (init, restart on failure)
 * - Status tracking
 *
 * @module wasm/pool/worker-pool
 */

import { WorkerId } from '@open-zentra/foundation-data-model';
import type { Logger } from '@open-zentra/foundation-utils';
import {
  createDebugLogger,
  getErrorMessage,
  normalizeError,
  withTimeout,
} from '@open-zentra/foundation-utils';

import { WorkerInitializationError } from '../../errors/pool-errors';
import type { ResolvedPoolConfig, WorkerInfo } from '../../types';
import { WorkerInstance } from './worker-instance';

// =============================================================================
// Circuit Breaker Constants
// =============================================================================

/** Maximum restart attempts per worker within the restart window */
const MAX_WORKER_RESTARTS = 3;

/** Time window (ms) in which MAX_WORKER_RESTARTS applies */
const RESTART_WINDOW_MS = 60_000;

// =============================================================================
// Worker Pool Manager Class
// =============================================================================

/**
 * Worker Pool Manager
 *
 * Manages multiple DuckDB worker instances and routes queries
 * to the least busy worker. Includes a per-worker restart circuit
 * breaker that prevents unbounded restart loops.
 */
export class WorkerPoolManager {
  private readonly workers = new Map<string, WorkerInstance>();
  private readonly config: ResolvedPoolConfig;
  private readonly logger: Logger;

  /** Per-worker restart timestamps for circuit breaker logic */
  private readonly restartHistory = new Map<string, number[]>();

  private workerIdCounter = 0;
  private initializing = false;
  private initialized = false;
  private shuttingDown = false;

  constructor(config: ResolvedPoolConfig) {
    this.config = config;
    this.logger = createDebugLogger('WorkerPool', config.debug);
  }

  // ===========================================================================
  // Lifecycle Methods
  // ===========================================================================

  /**
   * Initialize the worker pool with configured number of workers
   */
  async initialize(): Promise<void> {
    if (this.initialized || this.initializing) {
      return;
    }

    this.initializing = true;
    this.logger.info('Initializing pool', { workerCount: this.config.workerCount });

    const initPromises: Promise<WorkerInstance>[] = [];

    for (let i = 0; i < this.config.workerCount; i++) {
      initPromises.push(this.addWorker());
    }

    try {
      // Wait for all workers with timeout
      await withTimeout(
        Promise.all(initPromises),
        this.config.workerInitTimeout,
        `Worker pool initialization timed out after ${this.config.workerInitTimeout}ms`,
      );
      this.initialized = true;
      this.logger.info('Pool initialized successfully', {
        workerCount: this.workers.size,
      });
    } catch (error) {
      this.logger.error('Pool initialization failed', {
        error: getErrorMessage(error),
      });
      // Clean up any initialized workers
      await this.shutdown();
      throw error;
    } finally {
      this.initializing = false;
    }
  }

  /**
   * Check if the pool is ready
   */
  isReady(): boolean {
    return this.initialized && !this.shuttingDown;
  }

  /**
   * Shutdown all workers
   */
  async shutdown(): Promise<void> {
    if (this.shuttingDown) {
      return;
    }

    this.shuttingDown = true;
    this.logger.info('Shutting down pool', { workerCount: this.workers.size });

    const shutdownPromises: Promise<void>[] = [];

    for (const worker of this.workers.values()) {
      shutdownPromises.push(worker.shutdown());
    }

    await Promise.all(shutdownPromises);
    this.workers.clear();
    this.initialized = false;

    this.logger.info('Pool shutdown complete');
  }

  // ===========================================================================
  // Worker Management
  // ===========================================================================

  /**
   * Generate a unique worker ID
   */
  private generateWorkerId(): WorkerId {
    return WorkerId.create(++this.workerIdCounter);
  }

  /**
   * Add a new worker to the pool
   */
  async addWorker(): Promise<WorkerInstance> {
    const id = this.generateWorkerId();
    const worker = new WorkerInstance(id, { debug: this.config.debug });

    this.logger.debug('Adding worker', { workerId: id });
    this.workers.set(id, worker);

    try {
      await worker.initialize();
      this.logger.debug('Worker ready', { workerId: id });
      return worker;
    } catch (error) {
      this.workers.delete(id);
      const err = normalizeError(error);
      throw new WorkerInitializationError(id, err);
    }
  }

  /**
   * Remove a worker from the pool
   */
  async removeWorker(workerId: WorkerId | string): Promise<void> {
    const worker = this.workers.get(workerId);
    if (!worker) {
      return;
    }

    this.logger.debug('Removing worker', { workerId });
    await worker.shutdown();
    this.workers.delete(workerId);
  }

  /**
   * Check whether a worker is allowed to restart based on the circuit
   * breaker policy (MAX_WORKER_RESTARTS within RESTART_WINDOW_MS).
   */
  private isRestartAllowed(workerId: string): boolean {
    const now = Date.now();
    const history = this.restartHistory.get(workerId) ?? [];

    // Prune timestamps outside the window
    const recent = history.filter((t) => now - t < RESTART_WINDOW_MS);
    this.restartHistory.set(workerId, recent);

    return recent.length < MAX_WORKER_RESTARTS;
  }

  /**
   * Record a restart attempt for the circuit breaker.
   */
  private recordRestart(workerId: string): void {
    const history = this.restartHistory.get(workerId) ?? [];
    history.push(Date.now());
    this.restartHistory.set(workerId, history);
  }

  /**
   * Restart a failed worker.
   *
   * A per-worker circuit breaker limits restarts to MAX_WORKER_RESTARTS
   * within a RESTART_WINDOW_MS sliding window. When the limit is
   * exceeded the worker is left in error state and `null` is returned.
   */
  async restartWorker(workerId: WorkerId | string): Promise<WorkerInstance | null> {
    if (!this.config.restartFailedWorkers) {
      this.logger.debug('Worker restart disabled', { workerId });
      return null;
    }

    const worker = this.workers.get(workerId);
    if (!worker || worker.status !== 'error') {
      return null;
    }

    const workerIdStr = String(workerId);

    // Circuit breaker check
    if (!this.isRestartAllowed(workerIdStr)) {
      this.logger.warn('Worker restart circuit breaker open — too many restarts within window', {
        workerId,
        maxRestarts: MAX_WORKER_RESTARTS,
        windowMs: RESTART_WINDOW_MS,
      });
      return null;
    }

    this.logger.info('Restarting failed worker', { workerId });
    this.recordRestart(workerIdStr);

    // Remove the old worker
    await this.removeWorker(WorkerId.from(workerIdStr));

    // Add a new worker
    try {
      return await this.addWorker();
    } catch (error) {
      this.logger.error('Failed to restart worker', {
        workerId,
        error: getErrorMessage(error),
      });
      return null;
    }
  }

  /**
   * Check for failed workers and restart them
   */
  async checkAndRestartFailedWorkers(): Promise<void> {
    const failedWorkerIds: string[] = [];

    for (const [id, worker] of this.workers) {
      if (worker.status === 'error') {
        failedWorkerIds.push(id);
      }
    }

    for (const id of failedWorkerIds) {
      await this.restartWorker(WorkerId.from(id));
    }
  }

  // ===========================================================================
  // Worker Selection
  // ===========================================================================

  /**
   * Get the least busy worker
   *
   * Returns the worker with the shortest queue that is not in error state.
   * Returns null if no workers are available or all are at capacity.
   */
  getLeastBusyWorker(): WorkerInstance | null {
    let leastBusy: WorkerInstance | null = null;
    let minQueue = Infinity;

    for (const worker of this.workers.values()) {
      // Skip workers that are not ready
      if (worker.status !== 'idle' && worker.status !== 'busy') {
        continue;
      }

      // Check if worker is at capacity
      if (worker.queueLength >= this.config.maxQueuePerWorker) {
        continue;
      }

      // Find the one with the shortest queue
      if (worker.queueLength < minQueue) {
        minQueue = worker.queueLength;
        leastBusy = worker;
      }
    }

    return leastBusy;
  }

  /**
   * Get any available worker (even if at capacity)
   *
   * Used when we need to assign a query regardless of queue depth.
   */
  getAnyWorker(): WorkerInstance | null {
    let leastBusy: WorkerInstance | null = null;
    let minQueue = Infinity;

    for (const worker of this.workers.values()) {
      if (worker.status !== 'idle' && worker.status !== 'busy') {
        continue;
      }

      if (worker.queueLength < minQueue) {
        minQueue = worker.queueLength;
        leastBusy = worker;
      }
    }

    return leastBusy;
  }

  /**
   * Get a specific worker by ID
   */
  getWorker(workerId: WorkerId | string): WorkerInstance | undefined {
    return this.workers.get(workerId);
  }

  /**
   * Get all worker IDs
   */
  getWorkerIds(): string[] {
    return Array.from(this.workers.keys());
  }

  // ===========================================================================
  // Status
  // ===========================================================================

  /**
   * Get status of all workers
   */
  getWorkerStatus(): WorkerInfo[] {
    return Array.from(this.workers.values()).map((w) => w.getInfo());
  }

  /**
   * Get total number of workers
   */
  get workerCount(): number {
    return this.workers.size;
  }

  /**
   * Get number of active (non-error) workers
   */
  get activeWorkerCount(): number {
    let count = 0;
    for (const worker of this.workers.values()) {
      if (worker.status === 'idle' || worker.status === 'busy') {
        count++;
      }
    }
    return count;
  }

  /**
   * Get total queue length across all workers
   */
  get totalQueueLength(): number {
    let total = 0;
    for (const worker of this.workers.values()) {
      total += worker.queueLength;
    }
    return total;
  }

  /**
   * Check if all workers are at capacity
   */
  isAtCapacity(): boolean {
    for (const worker of this.workers.values()) {
      if (worker.status === 'idle' || worker.status === 'busy') {
        if (worker.queueLength < this.config.maxQueuePerWorker) {
          return false;
        }
      }
    }
    return true;
  }
}
