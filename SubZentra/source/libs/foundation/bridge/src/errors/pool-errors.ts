/**
 * Pool-related error classes
 *
 * @module errors/pool-errors
 */

import type { WorkerId } from '@open-zentra/foundation-data-model';
import { FOUNDATION_ERROR_CODE } from '@open-zentra/foundation-data-model';

import { BridgeError } from './base-error';

// =============================================================================
// Pool Shutdown Error
// =============================================================================

/**
 * Error thrown when trying to use a pool that is shutting down
 */
export class PoolShutdownError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_POOL_SHUTDOWN;

  constructor(readonly pendingQueries?: number) {
    super('Pool is shutting down, cannot accept new queries', {
      pendingQueries,
    });
  }
}

// =============================================================================
// Worker Error
// =============================================================================

/**
 * General error from a worker
 */
export class WorkerError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_WORKER_ERROR;

  constructor(readonly workerId: WorkerId, message: string, cause?: Error) {
    super(`Worker ${workerId}: ${message}`, { workerId }, cause);
  }
}

// =============================================================================
// Worker Initialization Error
// =============================================================================

/**
 * Error thrown when a worker fails to initialize
 */
export class WorkerInitializationError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_WORKER_INIT_FAILED;

  constructor(readonly workerId: WorkerId, cause: Error) {
    super(`Failed to initialize worker ${workerId}`, { workerId }, cause);
  }
}

// =============================================================================
// No Available Workers Error
// =============================================================================

/**
 * Error thrown when no workers are available to handle a query
 */
export class NoAvailableWorkersError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_WORKER_POOL_EXHAUSTED;

  constructor(readonly totalWorkers: number, readonly busyWorkers: number) {
    super(`No workers available (${busyWorkers}/${totalWorkers} busy)`, {
      totalWorkers,
      busyWorkers,
    });
  }
}

// =============================================================================
// Pool Capacity Error
// =============================================================================

/**
 * Error thrown when pool queue is at capacity
 */
export class PoolCapacityError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_POOL_AT_CAPACITY;

  constructor(readonly maxCapacity: number, readonly currentSize: number) {
    super(`Pool at capacity (${currentSize}/${maxCapacity})`, {
      maxCapacity,
      currentSize,
    });
  }
}
