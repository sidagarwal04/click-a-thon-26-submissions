/**
 * DuckDB Worker Pool Tests
 *
 * Unit tests for the worker pool implementation including:
 * - Priority queue
 * - Table lock manager
 * - Worker instance (mocked)
 * - Query coordinator (mocked)
 *
 * Note: Full integration tests require browser environment with Web Workers.
 *
 * @module wasm/pool/pool.spec
 */

import { beforeEach, describe, expect, it } from 'vitest';

import {
  Milliseconds,
  QueryCancelledError,
  QueryId,
  QueryTimeoutError,
  WorkerId,
} from '@open-zentra/foundation-data-model';

import { PoolShutdownError, WorkerError } from '../../errors/pool-errors';
import { PriorityQueue } from './priority-queue';
import { TableLockManager } from './table-lock-manager';

// =============================================================================
// Priority Queue Tests
// =============================================================================

describe('PriorityQueue', () => {
  let queue: PriorityQueue<string>;

  beforeEach(() => {
    queue = new PriorityQueue<string>();
  });

  describe('enqueue/dequeue', () => {
    it('should enqueue and dequeue items in FIFO order for same priority', () => {
      queue.enqueue('first', 'normal');
      queue.enqueue('second', 'normal');
      queue.enqueue('third', 'normal');

      expect(queue.dequeue()).toBe('first');
      expect(queue.dequeue()).toBe('second');
      expect(queue.dequeue()).toBe('third');
      expect(queue.dequeue()).toBeUndefined();
    });

    it('should dequeue high priority items before normal and low', () => {
      queue.enqueue('low-item', 'low');
      queue.enqueue('normal-item', 'normal');
      queue.enqueue('high-item', 'high');

      expect(queue.dequeue()).toBe('high-item');
      expect(queue.dequeue()).toBe('normal-item');
      expect(queue.dequeue()).toBe('low-item');
    });

    it('should handle mixed priorities correctly', () => {
      queue.enqueue('normal-1', 'normal');
      queue.enqueue('high-1', 'high');
      queue.enqueue('low-1', 'low');
      queue.enqueue('high-2', 'high');
      queue.enqueue('normal-2', 'normal');

      expect(queue.dequeue()).toBe('high-1');
      expect(queue.dequeue()).toBe('high-2');
      expect(queue.dequeue()).toBe('normal-1');
      expect(queue.dequeue()).toBe('normal-2');
      expect(queue.dequeue()).toBe('low-1');
    });
  });

  describe('peek', () => {
    it('should return the next item without removing it', () => {
      queue.enqueue('item1', 'normal');
      queue.enqueue('item2', 'normal');

      expect(queue.peek()).toBe('item1');
      expect(queue.peek()).toBe('item1'); // Still there
      expect(queue.size()).toBe(2);
    });

    it('should return undefined for empty queue', () => {
      expect(queue.peek()).toBeUndefined();
    });
  });

  describe('remove', () => {
    it('should remove item matching predicate', () => {
      queue.enqueue('keep1', 'normal');
      queue.enqueue('remove', 'normal');
      queue.enqueue('keep2', 'normal');

      const removed = queue.remove((item) => item === 'remove');

      expect(removed).toBe('remove');
      expect(queue.size()).toBe(2);
      expect(queue.dequeue()).toBe('keep1');
      expect(queue.dequeue()).toBe('keep2');
    });

    it('should return undefined if not found', () => {
      queue.enqueue('item1', 'normal');

      const removed = queue.remove((item) => item === 'nonexistent');

      expect(removed).toBeUndefined();
      expect(queue.size()).toBe(1);
    });
  });

  describe('size and isEmpty', () => {
    it('should track size correctly', () => {
      expect(queue.size()).toBe(0);
      expect(queue.isEmpty()).toBe(true);

      queue.enqueue('item1', 'high');
      expect(queue.size()).toBe(1);
      expect(queue.isEmpty()).toBe(false);

      queue.enqueue('item2', 'normal');
      expect(queue.size()).toBe(2);

      queue.dequeue();
      expect(queue.size()).toBe(1);

      queue.dequeue();
      expect(queue.size()).toBe(0);
      expect(queue.isEmpty()).toBe(true);
    });

    it('should track size by priority', () => {
      queue.enqueue('h1', 'high');
      queue.enqueue('h2', 'high');
      queue.enqueue('n1', 'normal');
      queue.enqueue('l1', 'low');

      expect(queue.sizeAt('high')).toBe(2);
      expect(queue.sizeAt('normal')).toBe(1);
      expect(queue.sizeAt('low')).toBe(1);
    });
  });

  describe('clear', () => {
    it('should clear all items and return them', () => {
      queue.enqueue('item1', 'high');
      queue.enqueue('item2', 'normal');
      queue.enqueue('item3', 'low');

      const cleared = queue.clear();

      expect(cleared).toHaveLength(3);
      expect(cleared).toContain('item1');
      expect(cleared).toContain('item2');
      expect(cleared).toContain('item3');
      expect(queue.isEmpty()).toBe(true);
    });
  });

  describe('iteration', () => {
    it('should iterate in priority order', () => {
      queue.enqueue('low', 'low');
      queue.enqueue('high', 'high');
      queue.enqueue('normal', 'normal');

      const items = [...queue];

      expect(items).toEqual(['high', 'normal', 'low']);
    });

    it('should convert to array', () => {
      queue.enqueue('a', 'normal');
      queue.enqueue('b', 'normal');

      expect(queue.toArray()).toEqual(['a', 'b']);
    });
  });
});

// =============================================================================
// Table Lock Manager Tests
// =============================================================================

describe('TableLockManager', () => {
  let lockManager: TableLockManager;

  beforeEach(() => {
    lockManager = new TableLockManager({ debug: false });
  });

  describe('read locks', () => {
    it('should allow multiple readers', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['users'], 'read');

      expect(lockManager.isLocked('users')).toBe(true);
      expect(lockManager.isWriteLocked('users')).toBe(false);
      expect(lockManager.getReaderCount('users')).toBe(2);
    });

    it('should release read locks correctly', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['users'], 'read');

      lockManager.releaseLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(1);

      lockManager.releaseLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(0);
      expect(lockManager.isLocked('users')).toBe(false);
    });
  });

  describe('write locks', () => {
    it('should provide exclusive write access', async () => {
      await lockManager.acquireLocks(['users'], 'write');

      expect(lockManager.isLocked('users')).toBe(true);
      expect(lockManager.isWriteLocked('users')).toBe(true);
    });

    it('should release write locks correctly', async () => {
      await lockManager.acquireLocks(['users'], 'write');
      lockManager.releaseLocks(['users'], 'write');

      expect(lockManager.isLocked('users')).toBe(false);
      expect(lockManager.isWriteLocked('users')).toBe(false);
    });
  });

  describe('lock contention', () => {
    it('should queue writers when readers hold locks', async () => {
      // Acquire read lock
      await lockManager.acquireLocks(['users'], 'read');

      // Writer should wait
      let writerAcquired = false;
      const writerPromise = lockManager.acquireLocks(['users'], 'write').then(() => {
        writerAcquired = true;
      });

      // Give time for async operations
      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(writerAcquired).toBe(false);

      // Release reader
      lockManager.releaseLocks(['users'], 'read');

      // Writer should now acquire
      await writerPromise;
      expect(writerAcquired).toBe(true);
      expect(lockManager.isWriteLocked('users')).toBe(true);
    });

    it('should queue readers when writer holds lock', async () => {
      // Acquire write lock
      await lockManager.acquireLocks(['users'], 'write');

      // Reader should wait
      let readerAcquired = false;
      const readerPromise = lockManager.acquireLocks(['users'], 'read').then(() => {
        readerAcquired = true;
      });

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(readerAcquired).toBe(false);

      // Release writer
      lockManager.releaseLocks(['users'], 'write');

      // Reader should now acquire
      await readerPromise;
      expect(readerAcquired).toBe(true);
      expect(lockManager.getReaderCount('users')).toBe(1);
    });
  });

  describe('multiple tables', () => {
    it('should handle multiple tables independently', async () => {
      await lockManager.acquireLocks(['users'], 'write');
      await lockManager.acquireLocks(['orders'], 'read');

      expect(lockManager.isWriteLocked('users')).toBe(true);
      expect(lockManager.isWriteLocked('orders')).toBe(false);
      expect(lockManager.getReaderCount('orders')).toBe(1);

      expect(lockManager.getLockedTables()).toContain('users');
      expect(lockManager.getLockedTables()).toContain('orders');
    });

    it('should acquire locks on multiple tables atomically', async () => {
      await lockManager.acquireLocks(['users', 'orders', 'products'], 'write');

      expect(lockManager.getLockedTables()).toHaveLength(3);
    });
  });

  describe('getLockStatus', () => {
    it('should return detailed lock status', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['orders'], 'write');

      const status = lockManager.getLockStatus();

      expect(status.get('users')).toEqual({
        readers: 2,
        writer: false,
        pendingReaders: 0,
        pendingWriters: 0,
      });

      expect(status.get('orders')).toEqual({
        readers: 0,
        writer: true,
        pendingReaders: 0,
        pendingWriters: 0,
      });
    });
  });

  describe('clearAll', () => {
    it('should clear all locks', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['orders'], 'write');

      lockManager.clearAll();

      expect(lockManager.getLockedTables()).toHaveLength(0);
    });
  });
});

// =============================================================================
// Error Types Tests
// =============================================================================

describe('Error Types', () => {
  it('should create QueryTimeoutError with correct properties', () => {
    const queryId = QueryId.from('query-123');
    const timeoutMs = Milliseconds.from(5000);
    const error = new QueryTimeoutError(queryId, timeoutMs);

    expect(error.name).toBe('QueryTimeoutError');
    expect(error.queryId).toBe('query-123');
    expect(error.timeoutMs).toBe(5000);
    expect(error.message).toContain('query-123');
    expect(error.message).toContain('5000');
  });

  it('should create QueryCancelledError with correct properties', () => {
    const queryId = QueryId.from('query-456');
    const error = new QueryCancelledError(queryId);

    expect(error.name).toBe('QueryCancelledError');
    expect(error.queryId).toBe('query-456');
    expect(error.message).toContain('cancelled');
  });

  it('should create WorkerError with correct properties', () => {
    const cause = new Error('Original error');
    const workerId = WorkerId.from('worker-1');
    const error = new WorkerError(workerId, 'Something went wrong', cause);

    expect(error.name).toBe('WorkerError');
    expect(error.workerId).toBe('worker-1');
    expect(error.cause).toBe(cause);
    expect(error.message).toContain('worker-1');
  });

  it('should create PoolShutdownError with correct properties', () => {
    const error = new PoolShutdownError();

    expect(error.name).toBe('PoolShutdownError');
    expect(error.message).toContain('shutting down');
  });
});
