/**
 * usePendingMutationCount Hook
 * Convenience hook to get pending offline mutation count.
 *
 * @module hooks/use-pending-mutation-count
 */

import { useDataLayer } from '../provider/data-layer-context';

/**
 * Hook to get the count of pending offline mutations
 *
 * Uses SyncCoordinator's queue manager from foundation-sync-engine.
 *
 * @returns The number of pending mutations
 *
 * @example
 * ```tsx
 * const pendingCount = usePendingMutationCount();
 *
 * if (pendingCount > 0) {
 *   return <SyncBadge count={pendingCount} />;
 * }
 * ```
 */
export const usePendingMutationCount = (): number => {
  const { pendingSyncCount } = useDataLayer();
  return pendingSyncCount;
};
