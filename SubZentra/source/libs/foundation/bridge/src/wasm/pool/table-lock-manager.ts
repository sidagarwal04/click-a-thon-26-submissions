/**
 * Table Lock Manager
 *
 * Manages read/write locks on tables for coordinating access across
 * multiple DuckDB worker instances sharing OPFS files.
 *
 * Lock semantics:
 * - Multiple readers can hold locks simultaneously
 * - Writers have exclusive access (no other readers or writers)
 * - Writers wait for all readers to finish
 * - Readers wait for writers to finish
 *
 * Adapted from meerkat-dbm's TableLockManager.
 *
 * @module wasm/pool/table-lock-manager
 */

import { createDebugLogger, type Logger } from '@open-zentra/foundation-utils';

import { QUERY_MODE } from '../../constants';
import type { QueryLockMode } from '../../constants';
import type { TableLockStatus } from '../../types/pool';

/**
 * Internal mutable table lock state
 * This is not exported - only TableLockStatus is public
 */
interface TableLock {
  readersCount: number;
  writer: boolean;
  readersQueue: Array<() => void>;
  writersQueue: Array<() => void>;
}

/**
 * Table Lock Manager for cross-worker coordination
 *
 * Implements a readers-writer lock pattern where:
 * - Multiple readers can access a table concurrently
 * - Writers get exclusive access
 * - Lock acquisition is fair (queued in order)
 */
export class TableLockManager {
  private tableLockRegistry: Map<string, TableLock> = new Map();
  private readonly logger: Logger;

  constructor(options: { debug?: boolean } = {}) {
    this.logger = createDebugLogger('TableLockManager', options.debug ?? false);
  }

  /**
   * Get or create a lock for a table
   */
  private getOrCreateLock(tableName: string): TableLock {
    let lock = this.tableLockRegistry.get(tableName);
    if (!lock) {
      lock = {
        readersCount: 0,
        writer: false,
        readersQueue: [],
        writersQueue: [],
      };
      this.tableLockRegistry.set(tableName, lock);
    }
    return lock;
  }

  /**
   * Acquire locks on multiple tables.
   *
   * Tables are sorted alphabetically before acquisition to establish a canonical
   * lock ordering. This prevents deadlocks when concurrent queries lock
   * overlapping sets of tables (e.g., Query A locks [X, Y] while Query B locks [Y, X]).
   *
   * @param tableNames - Tables to lock
   * @param mode - QUERY_MODE.READ for shared access, QUERY_MODE.WRITE for exclusive access
   * @returns Promise that resolves when all locks are acquired
   */
  async acquireLocks(
    tableNames: readonly string[],
    mode: QueryLockMode = QUERY_MODE.READ,
  ): Promise<void> {
    if (tableNames.length === 0) return;

    // Sort alphabetically to establish canonical lock ordering and prevent deadlocks
    const sortedTableNames = [...tableNames].sort();

    this.logger.debug(`Acquiring ${mode} locks on:`, sortedTableNames);

    const promises: Promise<void>[] = [];

    for (const tableName of sortedTableNames) {
      const tableLock = this.getOrCreateLock(tableName);

      if (mode === QUERY_MODE.READ) {
        // Can read if no writer currently holds the lock
        if (!tableLock.writer && tableLock.writersQueue.length === 0) {
          tableLock.readersCount++;
          this.logger.debug(`Read lock acquired immediately on ${tableName}`);
          continue;
        }

        // Wait for read access
        const promise = new Promise<void>((resolve) => {
          this.logger.debug(`Queuing read lock on ${tableName}`);
          tableLock.readersQueue.push(resolve);
        });
        promises.push(promise);
      } else {
        // Can write if no readers and no writer
        if (tableLock.readersCount === 0 && !tableLock.writer) {
          tableLock.writer = true;
          this.logger.debug(`Write lock acquired immediately on ${tableName}`);
          continue;
        }

        // Wait for write access
        const promise = new Promise<void>((resolve) => {
          this.logger.debug(`Queuing write lock on ${tableName}`);
          tableLock.writersQueue.push(resolve);
        });
        promises.push(promise);
      }
    }

    await Promise.all(promises);
    this.logger.debug(`All ${mode} locks acquired on:`, sortedTableNames);
  }

  /**
   * Release locks on multiple tables
   *
   * @param tableNames - Tables to unlock
   * @param mode - QUERY_MODE.READ or QUERY_MODE.WRITE (must match acquire mode)
   */
  releaseLocks(tableNames: readonly string[], mode: QueryLockMode = QUERY_MODE.READ): void {
    if (tableNames.length === 0) return;

    this.logger.debug(`Releasing ${mode} locks on:`, tableNames);

    for (const tableName of tableNames) {
      const tableLock = this.tableLockRegistry.get(tableName);
      if (!tableLock) continue;

      if (mode === QUERY_MODE.READ) {
        tableLock.readersCount--;

        // If no more readers, let a writer go
        if (tableLock.readersCount === 0 && tableLock.writersQueue.length > 0) {
          const nextWriter = tableLock.writersQueue.shift();
          if (nextWriter) {
            tableLock.writer = true;
            this.logger.debug(`Writer promoted on ${tableName}`);
            nextWriter();
          }
        }
      } else {
        tableLock.writer = false;

        // Readers first, then writers (prevents writer starvation of readers)
        if (tableLock.readersQueue.length > 0) {
          const readers = tableLock.readersQueue.splice(0);
          tableLock.readersCount += readers.length;
          this.logger.debug(`${readers.length} readers promoted on ${tableName}`);
          readers.forEach((reader) => reader());
        } else if (tableLock.writersQueue.length > 0) {
          const nextWriter = tableLock.writersQueue.shift();
          if (nextWriter) {
            tableLock.writer = true;
            this.logger.debug(`Writer promoted on ${tableName}`);
            nextWriter();
          }
        }
      }

      // Clean up registry entry if no activity (prevents unbounded growth)
      if (
        tableLock.readersCount === 0 &&
        !tableLock.writer &&
        tableLock.readersQueue.length === 0 &&
        tableLock.writersQueue.length === 0
      ) {
        this.tableLockRegistry.delete(tableName);
        this.logger.debug(`Cleaned up lock entry for ${tableName}`);
      }
    }
  }

  /**
   * Check if a table is currently locked
   *
   * @param tableName - Table to check
   * @returns True if the table has any active locks
   */
  isLocked(tableName: string): boolean {
    const tableLock = this.tableLockRegistry.get(tableName);
    return tableLock ? tableLock.readersCount > 0 || tableLock.writer : false;
  }

  /**
   * Check if a table has a write lock
   *
   * @param tableName - Table to check
   * @returns True if the table has an active write lock
   */
  isWriteLocked(tableName: string): boolean {
    const tableLock = this.tableLockRegistry.get(tableName);
    return tableLock?.writer ?? false;
  }

  /**
   * Get the number of active readers on a table
   *
   * @param tableName - Table to check
   * @returns Number of active readers
   */
  getReaderCount(tableName: string): number {
    const tableLock = this.tableLockRegistry.get(tableName);
    return tableLock?.readersCount ?? 0;
  }

  /**
   * Get all currently locked tables
   *
   * @returns Array of locked table names
   */
  getLockedTables(): string[] {
    const locked: string[] = [];
    for (const [tableName, lock] of this.tableLockRegistry) {
      if (lock.readersCount > 0 || lock.writer) {
        locked.push(tableName);
      }
    }
    return locked;
  }

  /**
   * Get lock status for all tables
   *
   * @returns Map of table names to read-only lock status
   */
  getLockStatus(): Map<string, TableLockStatus> {
    const status = new Map<string, TableLockStatus>();
    for (const [name, lock] of this.tableLockRegistry) {
      status.set(name, {
        readers: lock.readersCount,
        writer: lock.writer,
        pendingReaders: lock.readersQueue.length,
        pendingWriters: lock.writersQueue.length,
      });
    }
    return status;
  }

  /**
   * Clear all locks (use with caution, mainly for shutdown)
   */
  clearAll(): void {
    this.logger.debug('Clearing all locks');

    // Resolve all pending callbacks to unblock waiters
    for (const lock of this.tableLockRegistry.values()) {
      lock.readersQueue.forEach((resolve) => resolve());
      lock.writersQueue.forEach((resolve) => resolve());
    }

    this.tableLockRegistry.clear();
  }
}
