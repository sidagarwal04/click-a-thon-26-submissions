/**
 * Timer utilities
 *
 * Provides disposable timer utilities with automatic cleanup,
 * AbortSignal support, and statistics tracking.
 *
 * @module timer
 */

// Constants
export { TIME_MS, TIMER_DEFAULTS, TIMER_STATE } from './constants';
// Types from constants
export type { TimerState } from './constants';

// Types
export type {
  TimerStats,
  SafeTimerConfig,
  ManagedIntervalConfig,
  IntervalStats,
  SafeDebounceConfig,
  DebounceStats,
  ITimer,
  IDebounce,
} from './types';

// SafeTimer
export { SafeTimer, createSafeTimer, createOneShotTimer } from './safe-timer';

// ManagedInterval
export { ManagedInterval, createManagedInterval } from './managed-interval';

// SafeDebounce
export {
  SafeDebounce,
  createSafeDebounce,
  debounce,
  type DebouncedFunction,
} from './safe-debounce';
