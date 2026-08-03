/**
 * InsightsDatabase - Main Dexie database class
 *
 * Core database using Dexie for offline persistence.
 *
 * Key improvements:
 * - Uses ManagedInterval from foundation-utils for cleanup with automatic disposal
 * - Proper error handling (no silent swallowing)
 * - Consistent singleton pattern with config warning
 *
 * @module core/database
 */

import Dexie, { type Table } from 'dexie';
import isEqual from 'fast-deep-equal';

import {
  MUTATION_STATUS,
  type MutationQueueEntry,
  type TableSyncMetadataEntry,
} from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  createDeepEqualComparison,
  createSingletonFactory,
  ManagedInterval,
  type Logger,
} from '@open-zentra/foundation-utils';

import type { OpfsMetadataEntry } from '../tables/opfs-metadata';
import type { QueryCacheEntry } from '../tables/query-cache';
import type { SyncStateEntry } from '../tables/sync-state';
import type { DatabaseConfig } from './config';
import { mergeConfig } from './config';

/**
 * Main database class extending Dexie
 */
export class InsightsDatabase extends Dexie {
  /** Query cache table */
  queries!: Table<QueryCacheEntry, string>;

  /** Mutation queue table */
  mutations!: Table<MutationQueueEntry, string>;

  /** OPFS file metadata table */
  opfsFiles!: Table<OpfsMetadataEntry, string>;

  /** Sync state key-value table */
  syncState!: Table<SyncStateEntry, string>;

  /** Table sync metadata table (tracks parquet file sync state) */
  tableSyncMetadata!: Table<TableSyncMetadataEntry, string>;

  /** Database configuration */
  readonly config: DatabaseConfig;

  /** Cleanup interval using ManagedInterval for proper disposal */
  private cleanupInterval: ManagedInterval | null = null;

  /** Logger using foundation-utils createDebugLogger */
  private readonly logger: Logger;

  constructor(config: Partial<DatabaseConfig> = {}) {
    const mergedConfig = mergeConfig(config);
    super(mergedConfig.name);

    this.config = mergedConfig;
    this.logger = createDebugLogger('InsightsDatabase', mergedConfig.debug);

    // =========================================================================
    // DATABASE MIGRATIONS
    // =========================================================================
    //
    // IMPORTANT: When adding new versions, follow these rules:
    // 1. NEVER modify existing version schemas - add a new version
    // 2. Use .upgrade() for data transformations
    // 3. Test migrations in isolation before deployment
    // 4. Document the migration reason in comments
    //
    // Example of adding a new version:
    // this.version(2).stores({ ... }).upgrade(tx => { ... });
    //
    // =========================================================================

    // Version 1: Initial schema
    // - Query cache with hash-based lookup
    // - Mutation queue with dependency tracking
    // - OPFS file metadata
    // - Sync state key-value store
    this.version(1).stores({
      // Query cache: indexed by hash, with indexes for table name and timestamps
      queries: 'queryHash, tableName, dataUpdatedAt, expiresAt',

      // Mutation queue: indexed by id, with indexes for status, idempotency, and dependencies
      // *dependsOn is a multi-entry index for efficient dependency lookups
      mutations: 'id, timestamp, status, idempotencyKey, *dependsOn',

      // OPFS metadata: indexed by path
      opfsFiles: 'path, tableName, lastModified',

      // Sync state: simple key-value store
      syncState: 'key',
    });

    // Version 2: Add tableSyncMetadata table
    // Used by background file sync to track parquet file download state
    this.version(2).stores({
      queries: 'queryHash, tableName, dataUpdatedAt, expiresAt',
      mutations: 'id, timestamp, status, idempotencyKey, *dependsOn',
      opfsFiles: 'path, tableName, lastModified',
      syncState: 'key',
      // NEW: Table sync metadata for tracking parquet file sync state
      tableSyncMetadata: 'name, loadedAt',
    });

    // Version 3: Add indexes for hot query paths
    // - mutations: composite index for status+timestamp scans
    // - opfsFiles: indexes for registration and file-type lookups
    // - tableSyncMetadata: index for loadedAt timestamp comparisons
    this.version(3).stores({
      queries: 'queryHash, tableName, dataUpdatedAt, expiresAt',
      mutations: 'id, timestamp, status, [status+timestamp], idempotencyKey, *dependsOn',
      opfsFiles: 'path, tableName, lastModified, isRegistered, fileType',
      syncState: 'key',
      tableSyncMetadata: 'name, loadedAt, lastIngestedAt',
    });

    // Start cleanup if enabled
    if (mergedConfig.autoCleanup) {
      this.startCleanup();
    }

    this.log('Initialized', {
      name: mergedConfig.name,
      version: mergedConfig.version,
    });
  }

  /**
   * Log helper using foundation-utils logger
   */
  private log = (message: string, ...args: unknown[]): void => {
    this.logger.debug(message, ...args);
  };

  /**
   * Handle cleanup error
   * Always logs errors, not just in debug mode (fix for silent swallowing)
   */
  private handleCleanupError = (error: unknown): void => {
    this.logger.error('Cleanup error:', error);
  };

  /**
   * Get mutation IDs in terminal state before a timestamp cutoff.
   *
   * Uses the [status+timestamp] compound index to avoid collection scans.
   */
  private getTerminalMutationIdsBefore = async (
    status: typeof MUTATION_STATUS.COMPLETED | typeof MUTATION_STATUS.FAILED,
    cutoffTimestamp: number,
  ): Promise<string[]> => {
    const primaryKeys = await this.mutations
      .where('[status+timestamp]')
      .between([status, Dexie.minKey], [status, cutoffTimestamp], true, true)
      .primaryKeys();

    return primaryKeys.map((key) => String(key));
  };

  /**
   * Start automatic cleanup of expired entries
   *
   * Uses ManagedInterval for proper disposal and statistics tracking
   */
  startCleanup = (): void => {
    // Early return if already running
    if (this.cleanupInterval?.isActive) {
      return;
    }

    // Dispose existing interval if any (e.g., was stopped but not disposed)
    if (this.cleanupInterval) {
      this.cleanupInterval.dispose();
    }

    // Create new ManagedInterval with cleanup callback
    this.cleanupInterval = new ManagedInterval({
      interval: this.config.cleanupInterval,
      callback: async () => {
        try {
          await this.cleanup();
        } catch (error) {
          this.handleCleanupError(error);
        }
      },
      debug: this.config.debug,
    });

    this.cleanupInterval.start();
    this.log('Auto-cleanup started');
  };

  /**
   * Stop automatic cleanup
   *
   * Stops the ManagedInterval without disposing it
   */
  stopCleanup = (): void => {
    if (!this.cleanupInterval?.isActive) {
      return;
    }

    this.cleanupInterval.stop();
    this.log('Auto-cleanup stopped');
  };

  /**
   * Check if cleanup is running
   */
  isCleanupRunning = (): boolean => {
    return this.cleanupInterval?.isActive ?? false;
  };

  /**
   * Get cleanup statistics
   */
  getCleanupStats = (): { executionCount: number; lastExecutionAt: number | null } | null => {
    if (!this.cleanupInterval) {
      return null;
    }
    const stats = this.cleanupInterval.stats;
    return {
      executionCount: stats.executionCount,
      lastExecutionAt: stats.lastExecutionAt,
    };
  };

  /**
   * Cleanup expired query cache entries, apply LRU eviction, and purge
   * completed/failed mutations past their retention period.
   *
   * Three-stage cleanup:
   * 1. Delete all expired query entries (TTL-based)
   * 2. If still over maxCacheEntries, delete oldest queries (LRU-based)
   * 3. Delete completed/failed mutations older than mutationRetentionMs
   *
   * @returns Total number of entries deleted
   */
  cleanup = async (): Promise<number> => {
    let totalDeleted = 0;
    const now = Date.now();

    // Stage 1: Delete expired entries (TTL-based)
    const expiredCount = await this.queries.where('expiresAt').below(now).delete();

    totalDeleted += expiredCount;
    if (expiredCount > 0) {
      this.log(`Cleaned up ${expiredCount} expired queries`);
    }

    // Stage 2: LRU eviction if over limit
    if (this.config.maxCacheEntries > 0) {
      const currentCount = await this.queries.count();

      if (currentCount > this.config.maxCacheEntries) {
        const excessCount = currentCount - this.config.maxCacheEntries;

        // Get the oldest entries by dataUpdatedAt (LRU)
        const oldestEntries = await this.queries
          .orderBy('dataUpdatedAt')
          .limit(excessCount)
          .primaryKeys();

        if (oldestEntries.length > 0) {
          await this.queries.bulkDelete(oldestEntries);
          totalDeleted += oldestEntries.length;
          this.log(`LRU evicted ${oldestEntries.length} oldest cache entries`);
        }
      }
    }

    // Stage 3: Purge completed/failed mutations past retention period
    if (this.config.mutationRetentionMs > 0) {
      const retentionCutoff = now - this.config.mutationRetentionMs;
      const [completedIds, failedIds] = await Promise.all([
        this.getTerminalMutationIdsBefore(MUTATION_STATUS.COMPLETED, retentionCutoff),
        this.getTerminalMutationIdsBefore(MUTATION_STATUS.FAILED, retentionCutoff),
      ]);
      const staleMutations = [...completedIds, ...failedIds];

      if (staleMutations.length > 0) {
        await this.mutations.bulkDelete(staleMutations);
        totalDeleted += staleMutations.length;
        this.log(`Cleaned up ${staleMutations.length} completed/failed mutations`);
      }
    }

    return totalDeleted;
  };

  /**
   * Clear all data (useful for logout)
   *
   * Uses a transaction to ensure atomicity - either all tables are cleared
   * or none are (in case of error).
   */
  clearAll = async (): Promise<void> => {
    await this.transaction(
      'rw',
      [this.queries, this.mutations, this.opfsFiles, this.syncState, this.tableSyncMetadata],
      async () => {
        await Promise.all([
          this.queries.clear(),
          this.mutations.clear(),
          this.opfsFiles.clear(),
          this.syncState.clear(),
          this.tableSyncMetadata.clear(),
        ]);
      },
    );

    this.log('All data cleared');
  };

  /**
   * Get database statistics
   */
  getStats = async (): Promise<DatabaseStats> => {
    const [queriesCount, mutationsCount, opfsCount] = await Promise.all([
      this.queries.count(),
      this.mutations.count(),
      this.opfsFiles.count(),
    ]);

    const [pendingCount, offlineQueuedCount] = await Promise.all([
      this.mutations
        .where('[status+timestamp]')
        .between(
          [MUTATION_STATUS.PENDING, Dexie.minKey],
          [MUTATION_STATUS.PENDING, Dexie.maxKey],
          true,
          true,
        )
        .count(),
      this.mutations
        .where('[status+timestamp]')
        .between(
          [MUTATION_STATUS.OFFLINE_QUEUED, Dexie.minKey],
          [MUTATION_STATUS.OFFLINE_QUEUED, Dexie.maxKey],
          true,
          true,
        )
        .count(),
    ]);
    const pendingMutations = pendingCount + offlineQueuedCount;

    return {
      queriesCount,
      mutationsCount,
      opfsFilesCount: opfsCount,
      pendingMutations,
    };
  };

  /**
   * Close database and cleanup
   */
  override close(): void {
    // Dispose ManagedInterval (automatically stops and cleans up)
    if (this.cleanupInterval) {
      this.cleanupInterval.dispose();
      this.cleanupInterval = null;
    }
    super.close();
    this.log('Database closed');
  }
}

/**
 * Database statistics
 */
export interface DatabaseStats {
  queriesCount: number;
  mutationsCount: number;
  opfsFilesCount: number;
  pendingMutations: number;
}

// =============================================================================
// Singleton Management
// =============================================================================

/**
 * Singleton factory for InsightsDatabase
 */
const databaseFactory = createSingletonFactory(
  (config: Partial<DatabaseConfig> | undefined) => {
    return new InsightsDatabase(config);
  },
  {
    name: 'InsightsDatabase',
    compareConfig: createDeepEqualComparison(isEqual, 'InsightsDatabase'),
    onDispose: (instance) => {
      if (instance instanceof InsightsDatabase) {
        instance.close();
      }
    },
  },
);

/**
 * Get or create database instance
 *
 * Shared singleton source of truth for both getDatabase() and getDatabaseFacade().
 *
 * Note: If an instance already exists, the config parameter is ignored.
 * Call resetDatabase() first to change configuration.
 */
export const getDatabase = (config?: Partial<DatabaseConfig>): InsightsDatabase => {
  return databaseFactory.getInstance(config);
};

/**
 * Reset database instance
 *
 * Closes the current instance and clears the singleton.
 *
 * @returns Promise that resolves when reset is complete
 */
export const resetDatabase = async (): Promise<void> => {
  await databaseFactory.reset();
};

/**
 * Check if database instance exists
 */
export const hasDatabase = (): boolean => {
  return databaseFactory.hasInstance();
};
