/**
 * Deferred promise utilities
 *
 * Provides utilities for creating promises that can be resolved
 * or rejected externally.
 *
 * @module async/deferred
 */

/**
 * A promise that can be resolved or rejected from outside
 */
export interface Deferred<T> {
  /** The promise to await */
  readonly promise: Promise<T>;
  /** Resolve the promise with a value */
  readonly resolve: (value: T) => void;
  /** Reject the promise with an error */
  readonly reject: (error: Error) => void;
  /** Check if promise is still pending */
  readonly isPending: () => boolean;
}

/**
 * Create a deferred promise that can be resolved/rejected externally
 *
 * Useful for:
 * - Converting callback-based APIs to promises
 * - Coordinating between async operations
 * - Testing async code
 * - Creating manual promise resolution patterns
 *
 * @returns Deferred object with promise, resolve, reject, and isPending
 *
 * @example
 * ```typescript
 * const deferred = createDeferred<string>();
 *
 * // Pass the promise to some async consumer
 * someAsyncOperation(deferred.promise);
 *
 * // Later, resolve from elsewhere
 * deferred.resolve('done');
 *
 * // Or reject
 * deferred.reject(new Error('failed'));
 *
 * // Check if still pending
 * if (deferred.isPending()) {
 *   deferred.resolve('still waiting');
 * }
 * ```
 *
 * @example Timeout pattern
 * ```typescript
 * async function withTimeout<T>(
 *   operation: Promise<T>,
 *   ms: number
 * ): Promise<T> {
 *   const deferred = createDeferred<never>();
 *
 *   const timeoutId = setTimeout(() => {
 *     deferred.reject(new Error('Timeout'));
 *   }, ms);
 *
 *   try {
 *     return await Promise.race([operation, deferred.promise]);
 *   } finally {
 *     clearTimeout(timeoutId);
 *   }
 * }
 * ```
 */
export const createDeferred = <T>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  let settled = false;

  const promise = new Promise<T>((res, rej) => {
    resolve = (value: T) => {
      if (!settled) {
        settled = true;
        res(value);
      }
    };
    reject = (error: Error) => {
      if (!settled) {
        settled = true;
        rej(error);
      }
    };
  });

  return {
    promise,
    resolve,
    reject,
    isPending: () => !settled,
  };
};

/**
 * Create a deferred promise with automatic timeout
 *
 * @param timeoutMs - Timeout in milliseconds
 * @param timeoutMessage - Error message on timeout
 * @returns Deferred object that auto-rejects on timeout
 *
 * @example
 * ```typescript
 * const deferred = createDeferredWithTimeout<string>(5000, 'Response timeout');
 *
 * // Will auto-reject after 5 seconds if not resolved
 * eventEmitter.on('response', (data) => deferred.resolve(data));
 *
 * try {
 *   const result = await deferred.promise;
 * } catch (error) {
 *   // Handle timeout or other errors
 * }
 * ```
 */
export const createDeferredWithTimeout = <T>(
  timeoutMs: number,
  timeoutMessage = 'Operation timed out',
): Deferred<T> & { clearTimeout: () => void } => {
  const deferred = createDeferred<T>();

  const timeoutId = setTimeout(() => {
    deferred.reject(new Error(timeoutMessage));
  }, timeoutMs);

  return {
    ...deferred,
    clearTimeout: () => clearTimeout(timeoutId),
  };
};

/**
 * Sleep for a specified number of milliseconds
 *
 * A simple delay function that returns a promise that resolves after the specified time.
 * Also works with branded Milliseconds type from foundation-data-model.
 *
 * @param ms - Milliseconds to sleep (number or branded Milliseconds)
 * @returns Promise that resolves after the delay
 *
 * @example
 * ```typescript
 * await sleep(1000);
 * console.log('1 second passed');
 *
 * // Also works with Milliseconds branded type
 * await sleep(Milliseconds.from(1000));
 * ```
 */
export const sleep = (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

// =============================================================================
// Timeout Utilities
// =============================================================================

/**
 * Result of createTimeoutPromise, including a cleanup handle.
 */
export interface TimeoutPromiseResult<T> {
  /** Promise that rejects after the timeout */
  readonly promise: Promise<T>;
  /** Clear the underlying timer to prevent leaks */
  readonly cleanup: () => void;
}

/**
 * Create a promise that rejects after a timeout.
 *
 * Returns both the promise and a cleanup function. The caller MUST call
 * cleanup() when the timeout is no longer needed (e.g., after Promise.race
 * resolves) to prevent timer leaks.
 *
 * @param ms - Timeout in milliseconds
 * @param message - Optional error message
 * @returns Object with promise and cleanup function
 *
 * @example
 * ```typescript
 * const { promise, cleanup } = createTimeoutPromise(5000, 'Request timed out');
 * try {
 *   await Promise.race([operation, promise]);
 * } finally {
 *   cleanup();
 * }
 * ```
 */
export const createTimeoutPromise = <T = never>(
  ms: number,
  message?: string,
): TimeoutPromiseResult<T> => {
  let timerId: ReturnType<typeof setTimeout> | undefined;

  const promise = new Promise<T>((_, reject) => {
    timerId = setTimeout(() => {
      reject(new Error(message ?? `Operation timed out after ${ms}ms`));
    }, ms);
  });

  return {
    promise,
    cleanup: () => {
      if (timerId !== undefined) {
        clearTimeout(timerId);
        timerId = undefined;
      }
    },
  };
};

/**
 * Race a promise against a timeout.
 *
 * Automatically cleans up the timer after the race settles to prevent
 * timer leaks regardless of whether the operation or the timeout wins.
 *
 * @param promise - Promise to race
 * @param ms - Timeout in milliseconds
 * @param message - Optional error message
 * @returns Promise that resolves with value or rejects on timeout
 *
 * @example
 * ```typescript
 * const result = await withTimeout(
 *   fetchData(),
 *   5000,
 *   'Fetch timed out'
 * );
 * ```
 */
export const withTimeout = async <T>(
  promise: Promise<T>,
  ms: number,
  message?: string,
): Promise<T> => {
  const timeout = createTimeoutPromise<T>(ms, message);
  try {
    return await Promise.race([promise, timeout.promise]);
  } finally {
    timeout.cleanup();
  }
};

// =============================================================================
// Promise Utilities
// =============================================================================

/**
 * Run promises in sequence, one at a time
 *
 * Processes items sequentially, waiting for each promise to resolve
 * before starting the next one.
 *
 * @param items - Items to process
 * @param fn - Async function to run for each item
 * @returns Array of results in the same order as items
 *
 * @example
 * ```typescript
 * const urls = ['url1', 'url2', 'url3'];
 * const results = await runSequentially(urls, async (url) => {
 *   return fetch(url).then(r => r.json());
 * });
 * ```
 */
export const runSequentially = async <T, R>(
  items: readonly T[],
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> => {
  const results: R[] = [];
  for (let i = 0; i < items.length; i++) {
    results.push(await fn(items[i], i));
  }
  return results;
};

/**
 * Run promises with concurrency limit
 *
 * Processes items with a maximum number of concurrent operations.
 * Results are returned in the same order as the input items.
 *
 * @param items - Items to process
 * @param fn - Async function to run for each item
 * @param concurrency - Maximum concurrent operations
 * @returns Array of results in the same order as items
 *
 * @example
 * ```typescript
 * const urls = ['url1', 'url2', 'url3', 'url4', 'url5'];
 * // Process max 2 at a time
 * const results = await runWithConcurrency(urls, async (url) => {
 *   return fetch(url).then(r => r.json());
 * }, 2);
 * ```
 */
export const runWithConcurrency = async <T, R>(
  items: readonly T[],
  fn: (item: T, index: number) => Promise<R>,
  concurrency: number,
): Promise<R[]> => {
  const results: R[] = Array.from({ length: items.length });
  let currentIndex = 0;

  const worker = async (): Promise<void> => {
    while (currentIndex < items.length) {
      const index = currentIndex++;
      results[index] = await fn(items[index], index);
    }
  };

  const workers = Array.from({ length: Math.min(concurrency, items.length) }, () => worker());

  await Promise.all(workers);
  return results;
};
