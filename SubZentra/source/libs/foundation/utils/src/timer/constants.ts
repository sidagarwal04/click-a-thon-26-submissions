/**
 * Timer constants
 * @module timer/constants
 */

// =============================================================================
// Time Unit Constants (in milliseconds)
// =============================================================================

/**
 * Time unit constants in milliseconds
 *
 * Use these for calculations involving time durations.
 * All values are in milliseconds for consistency.
 *
 * @example
 * ```typescript
 * // Cache TTL of 24 hours
 * const cacheTTL = TIME_MS.DAY;
 *
 * // Stale time of 5 minutes
 * const staleTime = TIME_MS.MINUTE * 5;
 *
 * // Timeout of 30 seconds
 * const timeout = TIME_MS.SECOND * 30;
 * ```
 */
export const TIME_MS = {
  /** One second in milliseconds */
  SECOND: 1000,
  /** One minute in milliseconds */
  MINUTE: 1000 * 60,
  /** One hour in milliseconds */
  HOUR: 1000 * 60 * 60,
  /** One day in milliseconds */
  DAY: 1000 * 60 * 60 * 24,
  /** One week in milliseconds */
  WEEK: 1000 * 60 * 60 * 24 * 7,
} as const;

// =============================================================================
// Timer Configuration Defaults
// =============================================================================

/**
 * Default timer configuration values
 */
export const TIMER_DEFAULTS = {
  /** Default debounce delay in milliseconds */
  DEBOUNCE_DELAY_MS: 100,
  /** Default timeout in milliseconds */
  TIMEOUT_MS: 5000,
  /** Default interval in milliseconds */
  INTERVAL_MS: 1000,
  /** Maximum iterations for ManagedInterval (unlimited) */
  MAX_ITERATIONS: Infinity,
} as const;

/**
 * Timer state constant values
 */
export const TIMER_STATE = {
  IDLE: 'idle',
  RUNNING: 'running',
  PAUSED: 'paused',
  COMPLETED: 'completed',
  DISPOSED: 'disposed',
} as const;

/**
 * Timer state type derived from TIMER_STATE constants
 */
export type TimerState = (typeof TIMER_STATE)[keyof typeof TIMER_STATE];
