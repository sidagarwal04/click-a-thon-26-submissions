/**
 * Shared analytics routing contracts.
 *
 * @module contracts/analytics
 */

/**
 * Data freshness levels for analytics routing decisions.
 */
export const DATA_FRESHNESS = {
  REALTIME: 'REALTIME',
  NEAR_REALTIME: 'NEAR_REALTIME',
  EVENTUAL: 'EVENTUAL',
} as const;

/**
 * Data freshness type derived from `DATA_FRESHNESS`.
 */
export type DataFreshnessLevel = (typeof DATA_FRESHNESS)[keyof typeof DATA_FRESHNESS];
