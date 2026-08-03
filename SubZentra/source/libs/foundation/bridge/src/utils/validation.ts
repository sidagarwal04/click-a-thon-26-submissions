/**
 * Configuration validation utilities
 *
 * Import generic utilities directly from their source packages:
 * - From '@open-zentra/foundation-utils': deepFreeze, assert, assertDefined, isPositiveInteger, isNonNegative
 * - From '@open-zentra/foundation-data-model': ValidationResult, ValidationResultData
 *
 * @module utils/validation
 */

import {
  Milliseconds,
  ValidationResult,
  type ValidationResultData,
} from '@open-zentra/foundation-data-model';

import { BRIDGE_TYPE, DEFAULTS } from '../constants';
import type { BridgeType } from '../constants';
import type { DuckDBPoolConfig, ResolvedPoolConfig } from '../types/pool';

// =============================================================================
// Types
// =============================================================================

/**
 * Router configuration for validation
 */
export interface RouterConfigForValidation {
  readonly forceBridgeType?: BridgeType;
  readonly idleTimeout?: number;
  readonly debug?: boolean;
  readonly autoInit?: boolean;
}

// =============================================================================
// Validation Functions
// =============================================================================

/**
 * Validate pool configuration
 *
 * @param config - Configuration to validate
 * @returns Validation result with any errors
 */
export const validatePoolConfig = (config: DuckDBPoolConfig): ValidationResultData => {
  const errors: string[] = [];

  if (config.workerCount !== undefined) {
    if (!Number.isInteger(config.workerCount) || config.workerCount < 1) {
      errors.push('workerCount must be a positive integer');
    }
    if (config.workerCount > 16) {
      errors.push('workerCount should not exceed 16 (diminishing returns with more workers)');
    }
  }

  if (config.maxQueuePerWorker !== undefined) {
    if (!Number.isInteger(config.maxQueuePerWorker) || config.maxQueuePerWorker < 1) {
      errors.push('maxQueuePerWorker must be a positive integer');
    }
    if (config.maxQueuePerWorker > 100) {
      errors.push('maxQueuePerWorker should not exceed 100');
    }
  }

  if (config.maxActiveQueries !== undefined) {
    if (!Number.isInteger(config.maxActiveQueries) || config.maxActiveQueries < 1) {
      errors.push('maxActiveQueries must be a positive integer');
    }
    if (config.maxActiveQueries > 10000) {
      errors.push('maxActiveQueries should not exceed 10000');
    }
  }

  if (config.maxOverflowQueueSize !== undefined) {
    if (!Number.isInteger(config.maxOverflowQueueSize) || config.maxOverflowQueueSize < 1) {
      errors.push('maxOverflowQueueSize must be a positive integer');
    }
    if (config.maxOverflowQueueSize > 10000) {
      errors.push('maxOverflowQueueSize should not exceed 10000');
    }
  }

  if (config.defaultQueryTimeout !== undefined) {
    const ms = Milliseconds.unwrap(config.defaultQueryTimeout);
    if (ms < 0) {
      errors.push('defaultQueryTimeout must be non-negative');
    }
    if (ms > 300000) {
      errors.push('defaultQueryTimeout should not exceed 300000ms (5 minutes)');
    }
  }

  if (config.workerInitTimeout !== undefined) {
    const ms = Milliseconds.unwrap(config.workerInitTimeout);
    if (ms < 1000) {
      errors.push('workerInitTimeout should be at least 1000ms');
    }
    if (ms > 60000) {
      errors.push('workerInitTimeout should not exceed 60000ms');
    }
  }

  if (config.workerIdleTimeout !== undefined && config.workerIdleTimeout !== null) {
    if (Milliseconds.unwrap(config.workerIdleTimeout) < 0) {
      errors.push('workerIdleTimeout must be non-negative');
    }
  }

  return ValidationResult.fromErrors(errors);
};

/**
 * Validate router configuration
 *
 * @param config - Configuration to validate
 * @returns Validation result with any errors
 */
export const validateRouterConfig = (config: RouterConfigForValidation): ValidationResultData => {
  const errors: string[] = [];

  if (config.forceBridgeType !== undefined) {
    const validBridgeTypes: readonly string[] = Object.values(BRIDGE_TYPE);
    if (!validBridgeTypes.includes(config.forceBridgeType)) {
      errors.push(`forceBridgeType must be "${BRIDGE_TYPE.WASM}" or "${BRIDGE_TYPE.NATIVE}"`);
    }
  }

  if (config.idleTimeout !== undefined) {
    if (config.idleTimeout < 0) {
      errors.push('idleTimeout must be non-negative');
    }
    if (config.idleTimeout > 3600000) {
      errors.push('idleTimeout should not exceed 3600000ms (1 hour)');
    }
  }

  return ValidationResult.fromErrors(errors);
};

// =============================================================================
// Pool Config Resolution
// =============================================================================

/**
 * Resolve pool config with defaults
 */
export const resolvePoolConfig = (config: DuckDBPoolConfig): ResolvedPoolConfig => {
  return {
    workerCount:
      config.workerCount ?? (typeof navigator !== 'undefined' ? DEFAULTS.WORKER_COUNT : 2),
    maxQueuePerWorker: config.maxQueuePerWorker ?? DEFAULTS.MAX_QUEUE_PER_WORKER,
    maxActiveQueries: config.maxActiveQueries ?? 1000,
    maxOverflowQueueSize: config.maxOverflowQueueSize ?? 500,
    defaultQueryTimeout: config.defaultQueryTimeout ?? DEFAULTS.QUERY_TIMEOUT_MS,
    workerInitTimeout: config.workerInitTimeout ?? DEFAULTS.WORKER_INIT_TIMEOUT_MS,
    workerIdleTimeout: config.workerIdleTimeout ?? null,
    enableTableLocking: config.enableTableLocking ?? true,
    restartFailedWorkers: config.restartFailedWorkers ?? true,
    debug: config.debug ?? false,
  };
};
