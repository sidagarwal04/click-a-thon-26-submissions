/**
 * Database Facade
 *
 * Main entry point for interacting with the database.
 * Encapsulates all services and provides a clean API.
 *
 * @module facade/database-facade
 */

import type { TransactionMode } from 'dexie';
import isEqual from 'fast-deep-equal';

import {
  DATABASE_TRANSACTION_MODE,
  DATABASE_TRANSACTION_TABLE,
  type DatabaseTransactionMode,
  type DatabaseTransactionTable,
} from '@open-zentra/foundation-data-model';
import {
  assertNever,
  createDeepEqualComparison,
  createSingletonFactory,
} from '@open-zentra/foundation-utils';

import type { DatabaseConfig } from '../core/config';
import { getDatabase, resetDatabase, type DatabaseStats } from '../core/database';
import type { InsightsDatabase } from '../core/database';
import { MutationQueueService } from '../services/mutation-queue';
import { OpfsMetadataService } from '../services/opfs-metadata';
import { QueryCacheService } from '../services/query-cache';
import { SyncStateService } from '../services/sync-state';
import { TableSyncMetadataService } from '../services/table-sync-metadata';

const DEXIE_TRANSACTION_MODE_MAP: Record<DatabaseTransactionMode, TransactionMode> = {
  [DATABASE_TRANSACTION_MODE.READ]: 'r',
  [DATABASE_TRANSACTION_MODE.READ_WRITE]: 'rw',
};

/**
 * Database Facade
 *
 * Provides encapsulated access to all database services.
 * Use getDatabaseFacade() for singleton access.
 */
export class DatabaseFacade {
  /** Query cache service */
  readonly queries: QueryCacheService;

  /** Mutation queue service */
  readonly mutations: MutationQueueService;

  /** Sync state service */
  readonly syncState: SyncStateService;

  /** OPFS metadata service */
  readonly opfsMetadata: OpfsMetadataService;

  /** Table sync metadata service (tracks parquet file sync state) */
  readonly tableSyncMetadata: TableSyncMetadataService;

  /** Database configuration */
  readonly config: DatabaseConfig;

  private readonly db: InsightsDatabase;

  private constructor(db: InsightsDatabase) {
    this.db = db;
    this.config = db.config;
    this.queries = new QueryCacheService(db, db.config);
    this.mutations = new MutationQueueService(db, db.config);
    this.syncState = new SyncStateService(db, db.config);
    this.opfsMetadata = new OpfsMetadataService(db, db.config);
    this.tableSyncMetadata = new TableSyncMetadataService(db, db.config);
  }

  /**
   * Create a new DatabaseFacade instance
   */
  static create = (config?: Partial<DatabaseConfig>): DatabaseFacade => {
    return new DatabaseFacade(getDatabase(config));
  };

  /**
   * Get database statistics
   */
  getStats = async (): Promise<DatabaseStats> => {
    return this.db.getStats();
  };

  /**
   * Clear all data from all tables
   */
  clearAll = async (): Promise<void> => {
    await this.db.clearAll();
  };

  /**
   * Start auto-cleanup of expired data
   */
  startCleanup = (): void => {
    this.db.startCleanup();
  };

  /**
   * Stop auto-cleanup
   */
  stopCleanup = (): void => {
    this.db.stopCleanup();
  };

  /**
   * Run cleanup manually
   */
  cleanup = async (): Promise<number> => {
    return this.db.cleanup();
  };

  /**
   * Close the database connection
   */
  close = (): void => {
    this.db.close();
  };

  /**
   * Dispose facade resources.
   */
  dispose = (): void => {
    // Database singleton lifecycle is managed by core/database.ts.
  };

  /**
   * Get the underlying InsightsDatabase instance
   * Use this when you need to pass the database to other components
   * that require the raw database (e.g., SyncCoordinator)
   */
  getDatabase = (): InsightsDatabase => {
    return this.db;
  };

  /**
   * Execute operations within a transaction
   *
   * All operations in the callback function will be executed atomically.
   * If any operation fails, all changes will be rolled back.
   *
   * @param mode - Transaction mode constant value
   * @param tables - Transaction table constant values to include
   * @param fn - Async function containing the operations to execute
   * @returns The return value of the callback function
   *
   * @example
   * ```typescript
   * // Atomic update of cache and mutation queue
   * await facade.transaction(
   *   DATABASE_TRANSACTION_MODE.READ_WRITE,
   *   [DATABASE_TRANSACTION_TABLE.QUERIES, DATABASE_TRANSACTION_TABLE.MUTATIONS],
   *   async () => {
   *   await facade.queries.set(cacheEntry);
   *   await facade.mutations.add(mutationEntry);
   *   }
   * );
   * ```
   */
  private getTableReference = (table: DatabaseTransactionTable) => {
    switch (table) {
      case DATABASE_TRANSACTION_TABLE.QUERIES:
        return this.db.queries;
      case DATABASE_TRANSACTION_TABLE.MUTATIONS:
        return this.db.mutations;
      case DATABASE_TRANSACTION_TABLE.SYNC_STATE:
        return this.db.syncState;
      case DATABASE_TRANSACTION_TABLE.OPFS_FILES:
        return this.db.opfsFiles;
      case DATABASE_TRANSACTION_TABLE.TABLE_SYNC_METADATA:
        return this.db.tableSyncMetadata;
      default:
        return assertNever(table, 'Unknown transaction table');
    }
  };

  transaction = async <T>(
    mode: DatabaseTransactionMode,
    tables: DatabaseTransactionTable[],
    fn: () => Promise<T>,
  ): Promise<T> => {
    const tableRefs = tables.map((name) => this.getTableReference(name));
    return this.db.transaction(DEXIE_TRANSACTION_MODE_MAP[mode], tableRefs, fn);
  };
}

// =============================================================================
// Singleton Management
// =============================================================================

/**
 * Singleton factory for DatabaseFacade
 */
const facadeFactory = createSingletonFactory(
  (config: Partial<DatabaseConfig> | undefined) => {
    return DatabaseFacade.create(config);
  },
  {
    name: 'DatabaseFacade',
    compareConfig: createDeepEqualComparison(isEqual, 'DatabaseFacade'),
    onDispose: (instance) => {
      if (instance instanceof DatabaseFacade) {
        instance.dispose();
      }
    },
  },
);

/**
 * Get or create a singleton DatabaseFacade instance
 *
 * Note: If an instance already exists, the config parameter is ignored.
 * Call resetDatabaseFacade() first to change configuration.
 */
export const getDatabaseFacade = (config?: Partial<DatabaseConfig>): DatabaseFacade => {
  return facadeFactory.getInstance(config);
};

/**
 * Reset the singleton DatabaseFacade instance
 *
 * Clears the current instance and resets shared database state.
 * Next call to getDatabaseFacade() creates a new facade + database pair.
 *
 * Note: This also resets the shared database singleton so facade/core accessors
 * stay synchronized across lifecycle transitions.
 *
 * @returns Promise that resolves when reset is complete
 */
export const resetDatabaseFacade = async (): Promise<void> => {
  await facadeFactory.reset();
  await resetDatabase();
};

/**
 * Check if a facade instance exists
 */
export const hasDatabaseFacade = (): boolean => {
  return facadeFactory.hasInstance();
};
