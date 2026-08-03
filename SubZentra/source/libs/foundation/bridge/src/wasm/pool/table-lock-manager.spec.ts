/**
 * Tests for TableLockManager
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { TableLockManager } from './table-lock-manager';

describe('TableLockManager', () => {
  let lockManager: TableLockManager;

  beforeEach(() => {
    lockManager = new TableLockManager({ debug: false });
  });

  describe('acquireLocks (read mode)', () => {
    it('should acquire read lock immediately when no locks exist', async () => {
      await lockManager.acquireLocks(['users'], 'read');

      expect(lockManager.isLocked('users')).toBe(true);
      expect(lockManager.getReaderCount('users')).toBe(1);
    });

    it('should allow multiple concurrent readers', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['users'], 'read');

      expect(lockManager.getReaderCount('users')).toBe(3);
      expect(lockManager.isWriteLocked('users')).toBe(false);
    });

    it('should acquire locks on multiple tables', async () => {
      await lockManager.acquireLocks(['users', 'posts', 'comments'], 'read');

      expect(lockManager.isLocked('users')).toBe(true);
      expect(lockManager.isLocked('posts')).toBe(true);
      expect(lockManager.isLocked('comments')).toBe(true);
    });

    it('should handle empty table list', async () => {
      await expect(lockManager.acquireLocks([], 'read')).resolves.toBeUndefined();
    });
  });

  describe('acquireLocks (write mode)', () => {
    it('should acquire write lock immediately when no locks exist', async () => {
      await lockManager.acquireLocks(['users'], 'write');

      expect(lockManager.isLocked('users')).toBe(true);
      expect(lockManager.isWriteLocked('users')).toBe(true);
    });

    it('should wait for readers to release before acquiring write lock', async () => {
      // Acquire read lock first
      await lockManager.acquireLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(1);

      // Start write lock acquisition (will wait)
      let writeAcquired = false;
      const writePromise = lockManager.acquireLocks(['users'], 'write').then(() => {
        writeAcquired = true;
      });

      // Write should not be acquired yet
      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(writeAcquired).toBe(false);

      // Release read lock
      lockManager.releaseLocks(['users'], 'read');

      // Now write should be acquired
      await writePromise;
      expect(writeAcquired).toBe(true);
      expect(lockManager.isWriteLocked('users')).toBe(true);
    });
  });

  describe('releaseLocks', () => {
    it('should release read lock', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(1);

      lockManager.releaseLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(0);
    });

    it('should release write lock', async () => {
      await lockManager.acquireLocks(['users'], 'write');
      expect(lockManager.isWriteLocked('users')).toBe(true);

      lockManager.releaseLocks(['users'], 'write');
      expect(lockManager.isWriteLocked('users')).toBe(false);
    });

    it('should promote waiting writer when last reader releases', async () => {
      // Acquire read lock
      await lockManager.acquireLocks(['users'], 'read');

      // Queue a writer
      let writerAcquired = false;
      const writerPromise = lockManager.acquireLocks(['users'], 'write').then(() => {
        writerAcquired = true;
      });

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(writerAcquired).toBe(false);

      // Release read lock
      lockManager.releaseLocks(['users'], 'read');

      // Writer should be promoted
      await writerPromise;
      expect(writerAcquired).toBe(true);
      expect(lockManager.isWriteLocked('users')).toBe(true);
    });

    it('should promote waiting readers when writer releases', async () => {
      // Acquire write lock
      await lockManager.acquireLocks(['users'], 'write');

      // Queue readers
      let reader1Acquired = false;
      let reader2Acquired = false;
      const reader1Promise = lockManager.acquireLocks(['users'], 'read').then(() => {
        reader1Acquired = true;
      });
      const reader2Promise = lockManager.acquireLocks(['users'], 'read').then(() => {
        reader2Acquired = true;
      });

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(reader1Acquired).toBe(false);
      expect(reader2Acquired).toBe(false);

      // Release write lock
      lockManager.releaseLocks(['users'], 'write');

      // Both readers should be promoted
      await Promise.all([reader1Promise, reader2Promise]);
      expect(reader1Acquired).toBe(true);
      expect(reader2Acquired).toBe(true);
      expect(lockManager.getReaderCount('users')).toBe(2);
    });

    it('should handle releasing non-existent lock gracefully', () => {
      expect(() => lockManager.releaseLocks(['nonexistent'], 'read')).not.toThrow();
    });
  });

  describe('status methods', () => {
    it('should report isLocked correctly', async () => {
      expect(lockManager.isLocked('users')).toBe(false);

      await lockManager.acquireLocks(['users'], 'read');
      expect(lockManager.isLocked('users')).toBe(true);

      lockManager.releaseLocks(['users'], 'read');
      expect(lockManager.isLocked('users')).toBe(false);
    });

    it('should report isWriteLocked correctly', async () => {
      expect(lockManager.isWriteLocked('users')).toBe(false);

      await lockManager.acquireLocks(['users'], 'read');
      expect(lockManager.isWriteLocked('users')).toBe(false);

      lockManager.releaseLocks(['users'], 'read');
      await lockManager.acquireLocks(['users'], 'write');
      expect(lockManager.isWriteLocked('users')).toBe(true);
    });

    it('should report getReaderCount correctly', async () => {
      expect(lockManager.getReaderCount('users')).toBe(0);

      await lockManager.acquireLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(1);

      await lockManager.acquireLocks(['users'], 'read');
      expect(lockManager.getReaderCount('users')).toBe(2);
    });

    it('should report getLockedTables correctly', async () => {
      expect(lockManager.getLockedTables()).toEqual([]);

      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['posts'], 'write');

      const locked = lockManager.getLockedTables();
      expect(locked).toContain('users');
      expect(locked).toContain('posts');
    });

    it('should report getLockStatus correctly', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['posts'], 'write');

      const status = lockManager.getLockStatus();

      const usersStatus = status.get('users');
      expect(usersStatus?.readers).toBe(1);
      expect(usersStatus?.writer).toBe(false);

      const postsStatus = status.get('posts');
      expect(postsStatus?.readers).toBe(0);
      expect(postsStatus?.writer).toBe(true);
    });
  });

  describe('clearAll', () => {
    it('should clear all locks', async () => {
      await lockManager.acquireLocks(['users'], 'read');
      await lockManager.acquireLocks(['posts'], 'write');

      lockManager.clearAll();

      expect(lockManager.getLockedTables()).toEqual([]);
    });

    it('should resolve pending waiters', async () => {
      await lockManager.acquireLocks(['users'], 'write');

      let readerResolved = false;
      lockManager.acquireLocks(['users'], 'read').then(() => {
        readerResolved = true;
      });

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(readerResolved).toBe(false);

      lockManager.clearAll();

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(readerResolved).toBe(true);
    });
  });

  describe('writer starvation prevention', () => {
    it('should give readers priority over writers after writer releases', async () => {
      // Writer holds lock
      await lockManager.acquireLocks(['users'], 'write');

      // Queue a reader then a writer
      let readerAcquired = false;
      let writerAcquired = false;

      const readerPromise = lockManager.acquireLocks(['users'], 'read').then(() => {
        readerAcquired = true;
      });

      await new Promise((resolve) => setTimeout(resolve, 5));

      const writerPromise = lockManager.acquireLocks(['users'], 'write').then(() => {
        writerAcquired = true;
      });

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(readerAcquired).toBe(false);
      expect(writerAcquired).toBe(false);

      // Release current writer
      lockManager.releaseLocks(['users'], 'write');

      // Reader should be promoted first
      await readerPromise;
      expect(readerAcquired).toBe(true);

      // Release reader to let writer go
      lockManager.releaseLocks(['users'], 'read');

      await writerPromise;
      expect(writerAcquired).toBe(true);
    });
  });
});
