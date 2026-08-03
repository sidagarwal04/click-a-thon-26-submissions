/**
 * Shared conflict-resolution contracts.
 *
 * @module contracts/conflict-resolution
 */

/**
 * Conflict resolution values used by UI-level conflict workflows.
 */
export const CONFLICT_RESOLUTION_TYPE = {
  ACCEPT_LOCAL: 'accept-local',
  ACCEPT_REMOTE: 'accept-remote',
  MERGE: 'merge',
} as const;

/**
 * Conflict resolution type derived from `CONFLICT_RESOLUTION_TYPE`.
 */
export type ConflictResolutionType =
  (typeof CONFLICT_RESOLUTION_TYPE)[keyof typeof CONFLICT_RESOLUTION_TYPE];
