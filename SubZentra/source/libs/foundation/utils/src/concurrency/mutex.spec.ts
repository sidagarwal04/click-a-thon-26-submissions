/**
 * Tests for Mutex and Semaphore
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { Mutex, Semaphore } from './mutex';

describe('Mutex', () => {
  let mutex: Mutex;

  beforeEach(() => {
    mutex = new Mutex();
  });

  it('should not be locked initially', () => {
    expect(mutex.isLocked).toBe(false);
  });

  it('should be locked after acquire', async () => {
    await mutex.acquire();
    expect(mutex.isLocked).toBe(true);
  });

  it('should be unlocked after release', async () => {
    const release = await mutex.acquire();
    expect(mutex.isLocked).toBe(true);

    release();
    expect(mutex.isLocked).toBe(false);
  });

  it('should queue waiters when locked', async () => {
    const order: number[] = [];

    // First acquire
    const release1 = await mutex.acquire();
    order.push(1);

    // Second acquire should wait
    const promise2 = mutex.acquire().then((release) => {
      order.push(2);
      release();
    });

    // Third acquire should also wait
    const promise3 = mutex.acquire().then((release) => {
      order.push(3);
      release();
    });

    // Release first lock
    release1();

    await Promise.all([promise2, promise3]);

    expect(order).toEqual([1, 2, 3]);
  });

  it('should execute runExclusive in sequence', async () => {
    const results: string[] = [];

    const promise1 = mutex.runExclusive(async () => {
      await new Promise((r) => setTimeout(r, 50));
      results.push('first');
      return 'first';
    });

    const promise2 = mutex.runExclusive(async () => {
      results.push('second');
      return 'second';
    });

    const [result1, result2] = await Promise.all([promise1, promise2]);

    expect(result1).toBe('first');
    expect(result2).toBe('second');
    expect(results).toEqual(['first', 'second']);
  });

  it('should release lock even if function throws', async () => {
    await expect(
      mutex.runExclusive(async () => {
        throw new Error('test error');
      }),
    ).rejects.toThrow('test error');

    expect(mutex.isLocked).toBe(false);
  });

  describe('tryAcquire', () => {
    it('should return release function when not locked', () => {
      const release = mutex.tryAcquire();

      expect(release).not.toBeNull();
      expect(mutex.isLocked).toBe(true);

      release!();
      expect(mutex.isLocked).toBe(false);
    });

    it('should return null when already locked', async () => {
      await mutex.acquire();

      const result = mutex.tryAcquire();

      expect(result).toBeNull();
    });
  });
});

describe('Semaphore', () => {
  it('should throw for permits less than 1', () => {
    expect(() => new Semaphore(0)).toThrow('Semaphore must have at least 1 permit');
    expect(() => new Semaphore(-1)).toThrow('Semaphore must have at least 1 permit');
  });

  it('should have correct initial available permits', () => {
    const semaphore = new Semaphore(3);
    expect(semaphore.available).toBe(3);
  });

  it('should decrease available permits on acquire', async () => {
    const semaphore = new Semaphore(3);

    await semaphore.acquire();
    expect(semaphore.available).toBe(2);

    await semaphore.acquire();
    expect(semaphore.available).toBe(1);
  });

  it('should increase available permits on release', async () => {
    const semaphore = new Semaphore(3);

    const release1 = await semaphore.acquire();
    const release2 = await semaphore.acquire();
    expect(semaphore.available).toBe(1);

    release1();
    expect(semaphore.available).toBe(2);

    release2();
    expect(semaphore.available).toBe(3);
  });

  it('should queue when no permits available', async () => {
    const semaphore = new Semaphore(1);
    const order: number[] = [];

    const release1 = await semaphore.acquire();
    order.push(1);

    const promise2 = semaphore.acquire().then((release) => {
      order.push(2);
      return release;
    });

    // Should not have acquired yet
    await new Promise((r) => setTimeout(r, 10));
    expect(order).toEqual([1]);

    release1();
    const release2 = await promise2;
    expect(order).toEqual([1, 2]);

    release2();
  });

  it('should allow concurrent access up to permit count', async () => {
    const semaphore = new Semaphore(3);
    let concurrent = 0;
    let maxConcurrent = 0;

    const tasks = Array.from({ length: 5 }, async () => {
      return semaphore.runWithPermit(async () => {
        concurrent++;
        maxConcurrent = Math.max(maxConcurrent, concurrent);
        await new Promise((r) => setTimeout(r, 50));
        concurrent--;
      });
    });

    await Promise.all(tasks);

    expect(maxConcurrent).toBe(3);
  });

  it('should release permit even if function throws', async () => {
    const semaphore = new Semaphore(1);

    await expect(
      semaphore.runWithPermit(async () => {
        throw new Error('test error');
      }),
    ).rejects.toThrow('test error');

    expect(semaphore.available).toBe(1);
  });
});
