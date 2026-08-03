/**
 * useIsOnline Hook
 * Convenience hook to check network online status.
 *
 * @module hooks/use-is-online
 */

import { useDataLayer } from '../provider/data-layer-context';

/**
 * Hook to check if the application is online
 *
 * Uses SyncCoordinator's network status from foundation-sync-engine.
 *
 * @returns `true` if online, `false` if offline
 *
 * @example
 * ```tsx
 * const isOnline = useIsOnline();
 *
 * return (
 *   <div>
 *     {!isOnline && <OfflineBanner />}
 *     <Content />
 *   </div>
 * );
 * ```
 */
export const useIsOnline = (): boolean => {
  const { isOnline } = useDataLayer();
  return isOnline;
};
