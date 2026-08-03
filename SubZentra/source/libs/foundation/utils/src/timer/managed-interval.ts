/**
 * ManagedInterval - Disposable interval with iteration limits
 * @module timer/managed-interval
 */

import { Disposable } from '../disposable/disposable';
import { createDebugLogger, type Logger } from '../logger';
import { TIMER_DEFAULTS, TIMER_STATE, type TimerState } from './constants';
import type { IntervalStats, ITimer, ManagedIntervalConfig } from './types';

/**
 * ManagedInterval - An interval that extends Disposable for automatic cleanup
 *
 * Features:
 * - Extends Disposable for automatic cleanup
 * - Configurable iteration limit
 * - AbortSignal support for external cancellation
 * - Prevents callback execution after disposal
 * - Statistics tracking for debugging
 * - Chainable API
 *
 * @example
 * ```typescript
 * const interval = new ManagedInterval({
 *   interval: 1000,
 *   callback: () => console.log('Tick!'),
 *   maxIterations: 10,
 * });
 *
 * interval.start();
 *
 * // Later, cleanup
 * interval.dispose();
 * ```
 */
export class ManagedInterval extends Disposable implements ITimer {
  private readonly config: Required<Omit<ManagedIntervalConfig, 'signal' | 'autoStart'>> & {
    signal?: AbortSignal;
    autoStart: boolean;
  };
  private readonly logger: Logger;
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private _state: TimerState = TIMER_STATE.IDLE;
  private abortHandler: (() => void) | null = null;
  private currentIteration = 0;
  private readonly _stats: IntervalStats = {
    startCount: 0,
    executionCount: 0,
    cancelCount: 0,
    restartCount: 0,
    lastExecutionAt: null,
    totalExecutionTime: 0,
    currentIteration: 0,
    maxIterations: Infinity,
    completedNaturally: false,
  };

  constructor(config: ManagedIntervalConfig) {
    super();
    this.config = {
      interval: config.interval,
      callback: config.callback,
      maxIterations: config.maxIterations ?? TIMER_DEFAULTS.MAX_ITERATIONS,
      signal: config.signal,
      immediate: config.immediate ?? false,
      debug: config.debug ?? false,
      autoStart: config.autoStart ?? false,
    };
    this._stats.maxIterations = this.config.maxIterations;
    this.logger = createDebugLogger('ManagedInterval', this.config.debug);

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
   * Current interval state
   */
  get state(): TimerState {
    return this._state;
  }

  /**
   * Whether the interval is currently running
   */
  get isActive(): boolean {
    return this._state === TIMER_STATE.RUNNING;
  }

  /**
   * Get remaining iterations (Infinity if unlimited)
   */
  get remainingIterations(): number {
    if (this.config.maxIterations === Infinity) {
      return Infinity;
    }
    return Math.max(0, this.config.maxIterations - this.currentIteration);
  }

  /**
   * Get interval statistics
   */
  get stats(): Readonly<IntervalStats> {
    return {
      ...this._stats,
      currentIteration: this.currentIteration,
    };
  }

  /**
   * Start the interval
   * @returns this for chaining
   */
  start(): this {
    this.ensureNotDisposed();

    if (this.config.signal?.aborted) {
      this.logger.debug('Cannot start: signal already aborted');
      return this;
    }

    if (this._state === TIMER_STATE.RUNNING) {
      this.logger.debug('Interval already running');
      return this;
    }

    this.clearInterval();
    this._state = TIMER_STATE.RUNNING;
    this._stats.startCount++;

    // Execute immediately if configured
    if (this.config.immediate) {
      void this.executeCallback();
    }

    this.intervalId = setInterval(() => {
      void this.executeCallback();
    }, this.config.interval);

    this.logger.debug('Started', {
      interval: this.config.interval,
      maxIterations: this.config.maxIterations,
    });
    return this;
  }

  /**
   * Stop the interval
   * @returns this for chaining
   */
  stop(): this {
    return this.cancel();
  }

  /**
   * Cancel the interval (alias for stop)
   * @returns this for chaining
   */
  cancel(): this {
    if (this._state !== TIMER_STATE.RUNNING) {
      return this;
    }

    this.clearInterval();
    this._state = TIMER_STATE.IDLE;
    this._stats.cancelCount++;

    this.logger.debug('Stopped');
    return this;
  }

  /**
   * Restart the interval (stop and start again, resetting iteration count)
   * @returns this for chaining
   */
  restart(): this {
    this.ensureNotDisposed();

    if (this._state === TIMER_STATE.RUNNING) {
      this.clearInterval();
      this._stats.restartCount++;
    }

    this.currentIteration = 0;
    this._stats.completedNaturally = false;

    return this.start();
  }

  /**
   * Reset iteration count without stopping
   */
  resetIterations(): this {
    this.currentIteration = 0;
    this._stats.completedNaturally = false;
    this.logger.debug('Iterations reset');
    return this;
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

    // Check iteration limit
    if (this.currentIteration >= this.config.maxIterations) {
      this.logger.debug('Max iterations reached');
      this._stats.completedNaturally = true;
      this.stop();
      this._state = TIMER_STATE.COMPLETED;
      return;
    }

    this.currentIteration++;
    this._stats.currentIteration = this.currentIteration;

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

    // Check again after execution
    if (this.currentIteration >= this.config.maxIterations) {
      this.logger.debug('Max iterations reached after execution');
      this._stats.completedNaturally = true;
      this.stop();
      this._state = TIMER_STATE.COMPLETED;
    }
  }

  /**
   * Handle abort signal
   */
  private handleAbort(): void {
    this.logger.debug('Abort signal received');
    this.stop();
    this._state = TIMER_STATE.DISPOSED;
  }

  /**
   * Clear the interval
   */
  private clearInterval(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Cleanup on dispose
   */
  protected onDispose(): void {
    this.clearInterval();
    this._state = TIMER_STATE.DISPOSED;

    // Remove abort signal listener
    if (this.config.signal && this.abortHandler) {
      this.config.signal.removeEventListener('abort', this.abortHandler);
      this.abortHandler = null;
    }

    this.logger.debug('Disposed', { stats: this.stats });
  }
}

/**
 * Create a ManagedInterval instance
 */
export const createManagedInterval = (config: ManagedIntervalConfig): ManagedInterval =>
  new ManagedInterval(config);
