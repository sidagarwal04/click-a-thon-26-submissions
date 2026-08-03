/**
 * Timer type definitions
 * @module timer/types
 */

import type { TimerState } from './constants';

/**
 * Statistics tracked by SafeTimer
 */
export interface TimerStats {
  /** Number of times the timer was started */
  startCount: number;
  /** Number of times the callback was executed */
  executionCount: number;
  /** Number of times the timer was cancelled */
  cancelCount: number;
  /** Number of times the timer was restarted */
  restartCount: number;
  /** Last execution timestamp (null if never executed) */
  lastExecutionAt: number | null;
  /** Total execution time in milliseconds */
  totalExecutionTime: number;
}

/**
 * Configuration options for SafeTimer
 */
export interface SafeTimerConfig {
  /** Delay in milliseconds before callback execution */
  delay: number;
  /** Callback to execute when timer fires */
  callback: () => void | Promise<void>;
  /** Optional AbortSignal for external cancellation */
  signal?: AbortSignal;
  /** Enable debug logging */
  debug?: boolean;
  /** Auto-start the timer on creation */
  autoStart?: boolean;
}

/**
 * Configuration options for ManagedInterval
 */
export interface ManagedIntervalConfig {
  /** Interval in milliseconds between executions */
  interval: number;
  /** Callback to execute on each interval */
  callback: () => void | Promise<void>;
  /** Maximum number of iterations (default: unlimited) */
  maxIterations?: number;
  /** Optional AbortSignal for external cancellation */
  signal?: AbortSignal;
  /** Execute callback immediately on start */
  immediate?: boolean;
  /** Enable debug logging */
  debug?: boolean;
  /** Auto-start on creation */
  autoStart?: boolean;
}

/**
 * Statistics tracked by ManagedInterval
 */
export interface IntervalStats extends TimerStats {
  /** Current iteration count */
  currentIteration: number;
  /** Maximum iterations (Infinity if unlimited) */
  maxIterations: number;
  /** Whether the interval completed all iterations */
  completedNaturally: boolean;
}

/**
 * Configuration options for SafeDebounce
 */
export interface SafeDebounceConfig<TArgs extends unknown[]> {
  /** Delay in milliseconds */
  delay: number;
  /** Callback to execute */
  callback: (...args: TArgs) => void | Promise<void>;
  /** Optional AbortSignal for external cancellation */
  signal?: AbortSignal;
  /** Execute on leading edge instead of trailing */
  leading?: boolean;
  /** Execute on trailing edge (default: true) */
  trailing?: boolean;
  /** Maximum wait time before forced execution */
  maxWait?: number;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Statistics tracked by SafeDebounce
 */
export interface DebounceStats extends TimerStats {
  /** Number of calls that were debounced (not executed) */
  debouncedCount: number;
  /** Number of forced executions due to maxWait */
  forcedExecutionCount: number;
  /** Number of flush calls */
  flushCount: number;
}

/**
 * Common interface for all timer types
 */
export interface ITimer {
  /** Current timer state */
  readonly state: TimerState;
  /** Whether the timer is currently active */
  readonly isActive: boolean;
  /** Whether the timer has been disposed */
  readonly isDisposed: boolean;
  /** Start the timer */
  start(): this;
  /** Cancel/stop the timer */
  cancel(): this;
}

/**
 * Interface for debounce utilities
 */
export interface IDebounce<TArgs extends unknown[] = []> {
  /** Current debounce state */
  readonly state: TimerState;
  /** Whether a debounced call is pending */
  readonly isPending: boolean;
  /** Whether a debounced call is pending (alias for isPending) */
  readonly isActive: boolean;
  /** Whether the debounce has been disposed */
  readonly isDisposed: boolean;
  /** Call the debounced function */
  call(...args: TArgs): void;
  /** Cancel pending debounced call */
  cancel(): this;
  /** Execute pending call immediately */
  flush(): this;
}
