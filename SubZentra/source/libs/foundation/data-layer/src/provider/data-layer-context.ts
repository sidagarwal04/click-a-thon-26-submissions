/**
 * Data Layer Public Context
 *
 * Provides public data layer state for app components.
 * This context exposes high-level state and actions that apps need.
 *
 * @module provider/data-layer-context
 */

import { createContext, useContext } from 'react';

import type { DataLayerContextValue } from '../core/types';

/**
 * Default context value (for SSR and error boundaries)
 */
const defaultContextValue: DataLayerContextValue = {
  isOnline: true,
  isInitialized: false,
  isDuckDBAvailable: false,
  isSyncing: false,
  pendingSyncCount: 0,
  lastSyncedAt: null,
  isLeader: false,
  syncState: null,
  syncNow: async () => {
    throw new Error('DataLayerProvider not initialized');
  },
  clearCache: async () => {
    throw new Error('DataLayerProvider not initialized');
  },
};

/**
 * Public context for data layer state
 *
 * @example
 * ```tsx
 * const { isOnline, isSyncing, syncNow } = useDataLayer();
 *
 * if (!isOnline) {
 *   return <OfflineBanner onSync={syncNow} />;
 * }
 * ```
 */
export const DataLayerContext = createContext<DataLayerContextValue>(defaultContextValue);

DataLayerContext.displayName = 'DataLayerContext';

/**
 * Hook to access public data layer state and actions
 *
 * @example
 * ```tsx
 * const {
 *   isOnline,
 *   isInitialized,
 *   isSyncing,
 *   pendingSyncCount,
 *   syncNow,
 *   clearCache
 * } = useDataLayer();
 *
 * if (!isInitialized) return <Loading />;
 * if (!isOnline) return <OfflineBanner onRetry={syncNow} />;
 * ```
 */
export const useDataLayer = (): DataLayerContextValue => {
  const context = useContext(DataLayerContext);
  if (!context) {
    throw new Error('useDataLayer must be used within a DataLayerProvider');
  }
  return context;
};
