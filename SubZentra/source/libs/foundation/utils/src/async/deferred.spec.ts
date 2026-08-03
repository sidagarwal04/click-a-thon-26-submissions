/**
 * Tests for deferred promise utilities
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createDeferred, createDeferredWithTimeout } from './deferred';

describe('createDeferred', () => {
  it('should create a pending promise', () => {
    const deferred = createDeferred<string>();

    expect(deferred.isPending()).toBe(true);
  });

  it('should resolve the promise', async () => {
    const deferred = createDeferred<string>();

    deferred.resolve('test value');

    const result = await deferred.promise;
    expect(result).toBe('test value');
    expect(deferred.isPending()).toBe(false);
  });

  it('should reject the promise', async () => {
    const deferred = createDeferred<string>();

    deferred.reject(new Error('test error'));

    await expect(deferred.promise).rejects.toThrow('test error');
    expect(deferred.isPending()).toBe(false);
  });

  it('should ignore subsequent resolves', async () => {
    const deferred = createDeferred<string>();

    deferred.resolve('first');
    deferred.resolve('second');

    const result = await deferred.promise;
    expect(result).toBe('first');
  });

  it('should ignore subsequent rejects', async () => {
    const deferred = createDeferred<string>();

    deferred.reject(new Error('first'));
    deferred.reject(new Error('second'));

    await expect(deferred.promise).rejects.toThrow('first');
  });

  it('should ignore resolve after reject', async () => {
    const deferred = createDeferred<string>();

    deferred.reject(new Error('rejected'));
    deferred.resolve('resolved');

    await expect(deferred.promise).rejects.toThrow('rejected');
  });

  it('should ignore reject after resolve', async () => {
    const deferred = createDeferred<string>();

    deferred.resolve('resolved');
    deferred.reject(new Error('rejected'));

    const result = await deferred.promise;
    expect(result).toBe('resolved');
  });

  it('should work with typed values', async () => {
    interface User {
      id: number;
      name: string;
    }

    const deferred = createDeferred<User>();

    deferred.resolve({ id: 1, name: 'Test' });

    const result = await deferred.promise;
    expect(result.id).toBe(1);
    expect(result.name).toBe('Test');
  });
});

describe('createDeferredWithTimeout', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should auto-reject after timeout', async () => {
    const deferred = createDeferredWithTimeout<string>(1000);

    const promiseResult = deferred.promise.catch((e) => e);

    vi.advanceTimersByTime(1001);

    const error = await promiseResult;
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe('Operation timed out');
  });

  it('should use custom timeout message', async () => {
    const deferred = createDeferredWithTimeout<string>(1000, 'Custom timeout');

    const promiseResult = deferred.promise.catch((e) => e);

    vi.advanceTimersByTime(1001);

    const error = await promiseResult;
    expect(error.message).toBe('Custom timeout');
  });

  it('should not timeout if resolved first', async () => {
    const deferred = createDeferredWithTimeout<string>(1000);

    deferred.resolve('success');

    vi.advanceTimersByTime(2000);

    const result = await deferred.promise;
    expect(result).toBe('success');
  });

  it('should allow clearing timeout', async () => {
    const deferred = createDeferredWithTimeout<string>(1000);

    deferred.clearTimeout();

    vi.advanceTimersByTime(2000);

    // Promise should still be pending
    expect(deferred.isPending()).toBe(true);

    deferred.resolve('late resolution');
    const result = await deferred.promise;
    expect(result).toBe('late resolution');
  });
});
