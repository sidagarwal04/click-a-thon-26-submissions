/**
 * SafeTimer - Disposable timer with automatic cleanup
 * @module timer/safe-timer
 */

import { Disposable } from '../disposable/disposable';
import { createDebugLogger, type Logger } from '../logger';
import { TIMER_STATE, type TimerState } from './constants';
import type { ITimer, SafeTimerConfig, TimerStats } from './types';

/**
 * SafeTimer - A timer that extends Disposable for automatic cleanup
 *
 * Features:
 * - Extends Disposable for automatic cleanup
 * - AbortSignal support for external cancellation
 * - Prevents callback execution after disposal
 * - Statistics tracking for debugging
 * - Chainable API
 *
 * @example
 * ```typescript
 * const timer = new SafeTimer({
 *   delay: 1000,
 *   callback: () => console.log('Fired!'),
 * });
 *
 * timer.start();
 *
 * // Later, cleanup
 * timer.dispose();
 * ```
 */
export class SafeTimer extends Disposable implements ITimer {
  private readonly config: Required<Omit<SafeTimerConfig, 'signal' | 'autoStart'>> & {
    signal?: AbortSignal;
    autoStart: boolean;
  };
  private readonly logger: Logger;
  private timerId: ReturnType<typeof setTimeout> | null = null;
  private _state: TimerState = TIMER_STATE.IDLE;
  private abortHandler: (() => void) | null = null;
  private readonly _stats: TimerStats = {
    startCount: 0,
    executionCount: 0,
    cancelCount: 0,
    restartCount: 0,
    lastExecutionAt: null,
    totalExecutionTime: 0,
  };

  constructor(config: SafeTimerConfig) {
    super();
    this.config = {
      delay: config.delay,
      callback: config.callback,
      signal: config.signal,
      debug: config.debug ?? false,
      autoStart: config.autoStart ?? false,
    };
    this.logger = createDebugLogger('SafeTimer', this.config.debug);

    // Set up abort signal handler
    if (this.config.signal) {
      this.abortHandler = () => this.handleAbort();
      this.config.signal.addEventListener('abort', this.abortHandler);
    }

    if (this.config.autoStart) {
      this.start();
    }
  }

  /**
   * Current timer state
   */
  get state(): TimerState {
    return this._state;
  }

  /**
   * Whether the timer is currently running
   */
  get isActive(): boolean {
    return this._state === TIMER_STATE.RUNNING;
  }

  /**
   * Get timer statistics
   */
  get stats(): Readonly<TimerStats> {
    return { ...this._stats };
  }

  /**
   * Start the timer
   * @returns this for chaining
   */
  start(): this {
    this.ensureNotDisposed();

    if (this.config.signal?.aborted) {
      this.logger.debug('Cannot start: signal already aborted');
      return this;
    }

    if (this._state === TIMER_STATE.RUNNING) {
      this.logger.debug('Timer already running');
      return this;
    }

    this.clearTimer();
    this._state = TIMER_STATE.RUNNING;
    this._stats.startCount++;

    this.timerId = setTimeout(() => {
      this.executeCallback();
    }, this.config.delay);

    this.logger.debug('Started', { delay: this.config.delay });
    return this;
  }

  /**
   * Cancel the timer
   * @returns this for chaining
   */
  cancel(): this {
    if (this._state !== TIMER_STATE.RUNNING) {
      return this;
    }

    this.clearTimer();
    this._state = TIMER_STATE.IDLE;
    this._stats.cancelCount++;

    this.logger.debug('Cancelled');
    return this;
  }

  /**
   * Restart the timer (cancel and start again)
   * @returns this for chaining
   */
  restart(): this {
    this.ensureNotDisposed();

    if (this._state === TIMER_STATE.RUNNING) {
      this.clearTimer();
      this._stats.restartCount++;
    }

    return this.start();
  }

  /**
   * Execute the callback now, then cancel the timer
   */
  flush(): void {
    this.ensureNotDisposed();

    if (this._state !== TIMER_STATE.RUNNING) {
      this.logger.debug('Cannot flush: timer not running');
      return;
    }

    this.clearTimer();
    this.executeCallback();
  }

  /**
   * Execute the callback
   */
  private async executeCallback(): Promise<void> {
    if (this.isDisposed) {
      this.logger.debug('Skipping callback: disposed');
      return;
    }

    if (this.config.signal?.aborted) {
      this.logger.debug('Skipping callback: aborted');
      return;
    }

    this._state = TIMER_STATE.COMPLETED;
    this.timerId = null;

    const startTime = performance.now();
    this._stats.executionCount++;
    this._stats.lastExecutionAt = Date.now();

    try {
      await this.config.callback();
    } catch (error) {
      this.logger.error('Callback error:', error);
    } finally {
      this._stats.totalExecutionTime += performance.now() - startTime;
    }

    this.logger.debug('Callback executed');
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
   * Clear the timer
   */
  private clearTimer(): void {
    if (this.timerId !== null) {
      clearTimeout(this.timerId);
      this.timerId = null;
    }
  }

  /**
   * Cleanup on dispose
   */
  protected onDispose(): void {
    this.clearTimer();
    this._state = TIMER_STATE.DISPOSED;

    // Remove abort signal listener
    if (this.config.signal && this.abortHandler) {
      this.config.signal.removeEventListener('abort', this.abortHandler);
      this.abortHandler = null;
    }

    this.logger.debug('Disposed', { stats: this._stats });
  }
}

/**
 * Create a SafeTimer instance
 */
export const createSafeTimer = (config: SafeTimerConfig): SafeTimer => new SafeTimer(config);

/**
 * Create a one-shot timer that auto-disposes after execution
 */
export const createOneShotTimer = (
  delay: number,
  callback: () => void | Promise<void>,
  options?: { signal?: AbortSignal; debug?: boolean },
): SafeTimer => {
  const timer = new SafeTimer({
    delay,
    callback: async () => {
      try {
        await callback();
      } finally {
        timer.dispose();
      }
    },
    signal: options?.signal,
    debug: options?.debug,
    autoStart: true,
  });
  return timer;
};
