/**
 * SafeDebounce - Disposable debounce with automatic cleanup
 * @module timer/safe-debounce
 */

import { Disposable } from '../disposable/disposable';
import { createDebugLogger, type Logger } from '../logger';
import { TIMER_STATE, type TimerState } from './constants';
import type { DebounceStats, IDebounce, SafeDebounceConfig } from './types';

/**
 * SafeDebounce - A debounce utility that extends Disposable for automatic cleanup
 *
 * Features:
 * - Extends Disposable for automatic cleanup
 * - AbortSignal support for external cancellation
 * - Leading and trailing edge execution options
 * - Maximum wait time for forced execution
 * - Statistics tracking for debugging
 * - Prevents callback execution after disposal
 *
 * @example
 * ```typescript
 * const debounced = new SafeDebounce({
 *   delay: 300,
 *   callback: (value: string) => console.log('Search:', value),
 * });
 *
 * debounced.call('a');
 * debounced.call('ab');
 * debounced.call('abc'); // Only this one executes after 300ms
 *
 * // Later, cleanup
 * debounced.dispose();
 * ```
 */
export class SafeDebounce<TArgs extends unknown[] = []>
  extends Disposable
  implements IDebounce<TArgs>
{
  private readonly config: Required<Omit<SafeDebounceConfig<TArgs>, 'signal' | 'maxWait'>> & {
    signal?: AbortSignal;
    maxWait?: number;
  };
  private readonly logger: Logger;
  private timerId: ReturnType<typeof setTimeout> | null = null;
  private maxWaitTimerId: ReturnType<typeof setTimeout> | null = null;
  private _state: TimerState = TIMER_STATE.IDLE;
  private abortHandler: (() => void) | null = null;
  private lastArgs: TArgs | null = null;
  private lastCallTime: number | null = null;
  private leadingExecuted = false;
  private readonly _stats: DebounceStats = {
    startCount: 0,
    executionCount: 0,
    cancelCount: 0,
    restartCount: 0,
    lastExecutionAt: null,
    totalExecutionTime: 0,
    debouncedCount: 0,
    forcedExecutionCount: 0,
    flushCount: 0,
  };

  constructor(config: SafeDebounceConfig<TArgs>) {
    super();
    this.config = {
      delay: config.delay,
      callback: config.callback,
      signal: config.signal,
      leading: config.leading ?? false,
      trailing: config.trailing ?? true,
      maxWait: config.maxWait,
      debug: config.debug ?? false,
    };
    this.logger = createDebugLogger('SafeDebounce', this.config.debug);

    // Set up abort signal handler
    if (this.config.signal) {
      this.abortHandler = () => this.handleAbort();
      this.config.signal.addEventListener('abort', this.abortHandler);
    }
  }

  /**
   * Current debounce state
   */
  get state(): TimerState {
    return this._state;
  }

  /**
   * Whether a debounced call is pending
   */
  get isPending(): boolean {
    return this.timerId !== null;
  }

  /**
   * Whether a debounced call is pending (alias for isPending for API consistency)
   */
  get isActive(): boolean {
    return this.isPending;
  }

  /**
   * Get debounce statistics
   */
  get stats(): Readonly<DebounceStats> {
    return { ...this._stats };
  }

  /**
   * Call the debounced function
   */
  call(...args: TArgs): void {
    this.ensureNotDisposed();

    if (this.config.signal?.aborted) {
      this.logger.debug('Cannot call: signal aborted');
      return;
    }

    const now = Date.now();
    const isFirstCall = this.lastCallTime === null;
    this.lastCallTime = now;
    this.lastArgs = args;
    this._stats.startCount++;

    // Handle leading edge
    if (this.config.leading && isFirstCall && !this.leadingExecuted) {
      this.leadingExecuted = true;
      void this.executeCallback(args);
      this._state = TIMER_STATE.RUNNING;
    } else if (this.timerId !== null) {
      // Debouncing a call
      this._stats.debouncedCount++;
    }

    // Clear existing timer
    this.clearTimer();

    // Set up maxWait timer if configured and not already set
    if (this.config.maxWait !== undefined && this.maxWaitTimerId === null) {
      this.maxWaitTimerId = setTimeout(() => {
        this.maxWaitTimerId = null;
        if (this.lastArgs !== null && !this.isDisposed) {
          this._stats.forcedExecutionCount++;
          this.logger.debug('Forced execution due to maxWait');
          void this.executeCallback(this.lastArgs);
          this.reset();
        }
      }, this.config.maxWait);
    }

    // Set up trailing edge timer
    if (this.config.trailing) {
      this._state = TIMER_STATE.RUNNING;
      this.timerId = setTimeout(() => {
        this.timerId = null;
        if (this.lastArgs !== null && !this.isDisposed) {
          // Don't execute if leading already executed and no new calls came in
          if (!(this.config.leading && this.leadingExecuted && isFirstCall)) {
            void this.executeCallback(this.lastArgs);
          }
          this.reset();
        }
      }, this.config.delay);
    }

    this.logger.debug('Called', { delay: this.config.delay });
  }

  /**
   * Cancel pending debounced call
   * @returns this for chaining
   */
  cancel(): this {
    if (this.timerId === null && this.maxWaitTimerId === null) {
      return this;
    }

    this.clearTimer();
    this.clearMaxWaitTimer();
    this.reset();
    this._stats.cancelCount++;

    this.logger.debug('Cancelled');
    return this;
  }

  /**
   * Execute pending call immediately
   * @returns this for chaining
   */
  flush(): this {
    this.ensureNotDisposed();

    if (this.lastArgs === null) {
      this.logger.debug('Cannot flush: no pending call');
      return this;
    }

    this.clearTimer();
    this.clearMaxWaitTimer();
    this._stats.flushCount++;

    void this.executeCallback(this.lastArgs);
    this.reset();

    this.logger.debug('Flushed');
    return this;
  }

  /**
   * Execute the callback
   */
  private async executeCallback(args: TArgs): Promise<void> {
    if (this.isDisposed) {
      this.logger.debug('Skipping callback: disposed');
      return;
    }

    if (this.config.signal?.aborted) {
      this.logger.debug('Skipping callback: aborted');
      return;
    }

    const startTime = performance.now();
    this._stats.executionCount++;
    this._stats.lastExecutionAt = Date.now();

    try {
      await this.config.callback(...args);
    } catch (error) {
      this.logger.error('Callback error:', error);
    } finally {
      this._stats.totalExecutionTime += performance.now() - startTime;
    }
  }

  /**
   * Reset internal state
   */
  private reset(): void {
    this.lastArgs = null;
    this.lastCallTime = null;
    this.leadingExecuted = false;
    this._state = TIMER_STATE.IDLE;
  }

  /**
   * Handle abort signal
   */
  private handleAbort(): void {
    this.logger.debug('Abort signal received');
    this.cancel();
    this._state = TIMER_STATE.DISPOSED;
  }

  /**
   * Clear the debounce timer
   */
  private clearTimer(): void {
    if (this.timerId !== null) {
      clearTimeout(this.timerId);
      this.timerId = null;
    }
  }

  /**
   * Clear the max wait timer
   */
  private clearMaxWaitTimer(): void {
    if (this.maxWaitTimerId !== null) {
      clearTimeout(this.maxWaitTimerId);
      this.maxWaitTimerId = null;
    }
  }

  /**
   * Cleanup on dispose
   */
  protected onDispose(): void {
    this.clearTimer();
    this.clearMaxWaitTimer();
    this._state = TIMER_STATE.DISPOSED;
    this.lastArgs = null;

    // Remove abort signal listener
    if (this.config.signal && this.abortHandler) {
      this.config.signal.removeEventListener('abort', this.abortHandler);
      this.abortHandler = null;
    }

    this.logger.debug('Disposed', { stats: this._stats });
  }
}

/**
 * Create a SafeDebounce instance
 */
export const createSafeDebounce = <TArgs extends unknown[]>(
  config: SafeDebounceConfig<TArgs>,
): SafeDebounce<TArgs> => new SafeDebounce(config);

/**
 * Debounced function interface returned by the debounce factory
 */
export interface DebouncedFunction<TArgs extends unknown[]> {
  (...args: TArgs): void;
  /** Cancel pending debounced call */
  cancel(): void;
  /** Execute pending call immediately */
  flush(): void;
  /** Dispose the debounce instance */
  dispose(): void;
  /** Whether a debounced call is pending */
  readonly isPending: boolean;
  /** Whether a debounced call is pending (alias for isPending) */
  readonly isActive: boolean;
}

/**
 * Create a simple debounced function (returns a callable function)
 *
 * @example
 * ```typescript
 * const debouncedSearch = debounce(
 *   (query: string) => console.log('Search:', query),
 *   300
 * );
 *
 * debouncedSearch('a');
 * debouncedSearch('ab');
 * debouncedSearch('abc'); // Only this executes after 300ms
 *
 * // Check if pending
 * if (debouncedSearch.isPending) {
 *   debouncedSearch.cancel();
 * }
 *
 * // Cleanup
 * debouncedSearch.dispose();
 * ```
 */
export const debounce = <TArgs extends unknown[]>(
  callback: (...args: TArgs) => void | Promise<void>,
  delay: number,
  options?: Omit<SafeDebounceConfig<TArgs>, 'callback' | 'delay'>,
): DebouncedFunction<TArgs> => {
  const instance = new SafeDebounce({
    delay,
    callback,
    ...options,
  });

  const debouncedFn = ((...args: TArgs): void => {
    instance.call(...args);
  }) as DebouncedFunction<TArgs>;

  debouncedFn.cancel = (): void => {
    instance.cancel();
  };
  debouncedFn.flush = (): void => {
    instance.flush();
  };
  debouncedFn.dispose = (): void => {
    instance.dispose();
  };

  Object.defineProperty(debouncedFn, 'isPending', {
    get: () => instance.isPending,
    enumerable: true,
  });

  Object.defineProperty(debouncedFn, 'isActive', {
    get: () => instance.isActive,
    enumerable: true,
  });

  return debouncedFn;
};
