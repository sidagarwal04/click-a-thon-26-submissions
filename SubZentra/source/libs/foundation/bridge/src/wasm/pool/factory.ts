/**
 * DuckDB Pool Factory
 *
 * Factory functions for creating and managing DuckDB worker pool instances.
 *
 * @module wasm/pool/factory
 */

import { Milliseconds } from '@open-zentra/foundation-data-model';
import {
  createAsyncSingletonFactory,
  type ConfigComparisonResult,
} from '@open-zentra/foundation-utils';

import type { DuckDBPoolConfig } from '../../types/pool';
import { QueryCoordinator } from './query-coordinator';

/**
 * DuckDB Pool interface (public API)
 *
 * Provides a clean interface for interacting with the worker pool.
 */
export interface DuckDBPool {
  /** Execute a query */
  query: QueryCoordinator['query'];
  /** Get pool status */
  getStatus: QueryCoordinator['getStatus'];
  /** Get pool configuration */
  getConfig: QueryCoordinator['getConfig'];
  /** Check if pool is ready */
  isReady: QueryCoordinator['isReady'];
  /** Shutdown the pool */
  shutdown: QueryCoordinator['shutdown'];
}

/**
 * Create a new DuckDB worker pool
 *
 * @param config - Pool configuration
 * @returns Initialized DuckDB pool
 *
 * @example
 * ```typescript
 * const pool = await createDuckDBPool({
 *   workerCount: 3,
 *   maxQueuePerWorker: 10,
 *   defaultQueryTimeout: 30000,
 *   debug: true,
 * });
 *
 * const result = await pool.query({
 *   sql: 'SELECT * FROM users',
 *   tables: ['users'],
 *   mode: 'read',
 * });
 *
 * await pool.shutdown();
 * ```
 */
export const createDuckDBPool = async (config: DuckDBPoolConfig = {}): Promise<DuckDBPool> => {
  const coordinator = new QueryCoordinator(config);
  await coordinator.initialize();

  return {
    query: coordinator.query.bind(coordinator),
    getStatus: coordinator.getStatus.bind(coordinator),
    getConfig: coordinator.getConfig.bind(coordinator),
    isReady: coordinator.isReady.bind(coordinator),
    shutdown: coordinator.shutdown.bind(coordinator),
  };
};

/**
 * Check if config differences are significant enough to warrant a warning
 * Critical settings like workerCount affect pool behavior significantly
 */
const comparePoolConfig = (
  existingConfig: DuckDBPoolConfig | undefined,
  newConfig: DuckDBPoolConfig,
): ConfigComparisonResult => {
  if (!existingConfig) {
    return { shouldWarn: false };
  }

  const changes: string[] = [];

  // Critical settings that significantly affect behavior
  if (existingConfig.workerCount !== newConfig.workerCount && newConfig.workerCount !== undefined) {
    changes.push(`workerCount: ${existingConfig.workerCount} → ${newConfig.workerCount}`);
  }
  if (
    existingConfig.maxQueuePerWorker !== newConfig.maxQueuePerWorker &&
    newConfig.maxQueuePerWorker !== undefined
  ) {
    changes.push(
      `maxQueuePerWorker: ${existingConfig.maxQueuePerWorker} → ${newConfig.maxQueuePerWorker}`,
    );
  }
  if (
    newConfig.defaultQueryTimeout !== undefined &&
    existingConfig.defaultQueryTimeout !== undefined &&
    Milliseconds.unwrap(existingConfig.defaultQueryTimeout) !==
      Milliseconds.unwrap(newConfig.defaultQueryTimeout)
  ) {
    changes.push(
      `defaultQueryTimeout: ${Milliseconds.unwrap(
        existingConfig.defaultQueryTimeout,
      )} → ${Milliseconds.unwrap(newConfig.defaultQueryTimeout)}`,
    );
  }

  if (changes.length === 0) {
    return { shouldWarn: false };
  }

  return {
    shouldWarn: true,
    message:
      `[DuckDBPool] getDuckDBPool called with different config than existing pool.\n` +
      `Changed settings: ${changes.join(', ')}\n` +
      `Current pool configuration will be used. Call resetDuckDBPool() first to change configuration.`,
  };
};

/**
 * Singleton factory for DuckDB pool
 */
const poolFactory = createAsyncSingletonFactory(
  (config: DuckDBPoolConfig) => createDuckDBPool(config),
  {
    name: 'DuckDBPool',
    compareConfig: comparePoolConfig,
    onDispose: async (instance) => {
      if (
        instance &&
        typeof instance === 'object' &&
        'shutdown' in instance &&
        typeof instance.shutdown === 'function'
      ) {
        await instance.shutdown();
      }
    },
    defaultConfig: {},
  },
);

/**
 * Get or create a singleton DuckDB pool
 *
 * If a pool already exists, returns it. If the configuration differs
 * significantly from the existing pool, logs a warning (config is ignored).
 *
 * @param config - Pool configuration (only used if creating new pool)
 * @returns DuckDB pool instance
 *
 * @example
 * ```typescript
 * // First call creates the pool
 * const pool1 = await getDuckDBPool({ workerCount: 3 });
 *
 * // Subsequent calls return the same pool
 * const pool2 = await getDuckDBPool();
 * console.log(pool1 === pool2); // true
 *
 * // To change config, reset first
 * await resetDuckDBPool();
 * const pool3 = await getDuckDBPool({ workerCount: 5 });
 * ```
 */
export const getDuckDBPool = poolFactory.getInstance;

/**
 * Reset the singleton pool
 *
 * Shuts down the existing singleton pool if one exists.
 * The next call to getDuckDBPool will create a new pool.
 *
 * @example
 * ```typescript
 * // Shutdown existing pool
 * await resetDuckDBPool();
 *
 * // Create new pool with different config
 * const pool = await getDuckDBPool({ workerCount: 5 });
 * ```
 */
export const resetDuckDBPool = poolFactory.reset;

/**
 * Check if a pool instance exists
 */
export const hasDuckDBPool = poolFactory.hasInstance;
