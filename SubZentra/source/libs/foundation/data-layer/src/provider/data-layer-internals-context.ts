/**
 * Data Layer Internals Context
 *
 * Provides internal data layer state for hooks.
 * This context exposes low-level services that hooks need.
 *
 * Integrates with foundation libraries:
 * - foundation-database: DatabaseFacade
 * - foundation-sync-engine: SyncCoordinator
 * - foundation-bridge: DuckDBRouter
 *
 * @module provider/data-layer-internals-context
 */

import { createContext, useContext } from 'react';

import type { QueryClient } from '@tanstack/react-query';
import type { AxiosInstance } from 'axios';

import type { AuthScopeSnapshot } from '@open-zentra/foundation-auth';
import type { DuckDBRouter } from '@open-zentra/foundation-bridge';
import type { DatabaseFacade, OpfsManager } from '@open-zentra/foundation-database';
import type { SyncCoordinator } from '@open-zentra/foundation-sync-engine';

import type { FileDownloadService } from '../analytics-sync/file-download-service';
import type { TableSyncService } from '../analytics-sync/table-sync-service';
import type { TableRegistry } from '../core/table-registry';
import type {
  DataSourceEndpointDescriptor,
  RealtimeConnectionStateSnapshot,
  RealtimeMessageEnvelope,
  RealtimeSubscriptionStateMap,
  ResolvedCacheConfig,
} from '../core/types';
import type { RealtimeSocketClient, RealtimeSocketStatus } from '../realtime';

/**
 * Internal data layer state accessible by hooks
 *
 * Uses foundation libraries:
 * - DatabaseFacade from foundation-database for persistence
 * - SyncCoordinator from foundation-sync-engine for offline sync
 * - DuckDBRouter from foundation-bridge for analytics
 * - TableRegistry for unified table metadata
 */
export interface DataLayerInternals {
  /** TanStack Query client */
  readonly queryClient: QueryClient;

  /** Shared Axios instance */
  readonly axiosInstance: AxiosInstance;

  readonly authScope: AuthScopeSnapshot | null;
  readonly authScopeKey: string;

  /** Realtime socket client */
  readonly realtimeClient: RealtimeSocketClient;

  /** Current realtime socket status */
  readonly realtimeStatus: RealtimeSocketStatus;

  /** Current realtime connection snapshot */
  readonly realtimeConnection: RealtimeConnectionStateSnapshot;

  /** Current realtime subscription states */
  readonly realtimeSubscriptions: RealtimeSubscriptionStateMap;

  /** Last realtime message received */
  readonly lastRealtimeMessage: RealtimeMessageEnvelope | null;

  /** Database facade from foundation-database */
  readonly database: DatabaseFacade;

  /** Sync coordinator from foundation-sync-engine */
  readonly syncCoordinator: SyncCoordinator;

  /** DuckDB router from foundation-bridge (null if not available) */
  readonly duckdbRouter: DuckDBRouter | null;

  /** OPFS manager from foundation-database (null if not available) */
  readonly opfsManager: OpfsManager | null;

  /** Whether analytics runtime is enabled in config */
  readonly analyticsEnabled: boolean;

  /**
   * Lazily initialize analytics runtime.
   * Creates DuckDB + OPFS resources on first use.
   */
  readonly initializeAnalytics: () => Promise<{
    readonly duckdbRouter: DuckDBRouter;
    readonly opfsManager: OpfsManager | null;
  } | null>;

  /** Network online status */
  readonly isOnline: boolean;

  /** Resolved cache configuration */
  readonly cacheConfig: ResolvedCacheConfig;

  /**
   * Unified table registry - single source of truth for table metadata.
   * Used by DataLayer hooks, SyncEngine, and QueryEngine.
   */
  readonly tableRegistry: TableRegistry;

  /**
   * Global datasource endpoint descriptor for background file sync.
   * Used by useBackgroundFileSync to fetch parquet file metadata.
   * Null if not configured.
   */
  readonly datasourceEndpoint: DataSourceEndpointDescriptor | null;
  /** Container-scoped table sync service accessor */
  readonly getTableSyncService: () => TableSyncService;
  /** Container-scoped file download service accessor */
  readonly getFileDownloadService: () => Promise<FileDownloadService | null>;
}

/**
 * Internal context for hooks to access low-level data layer internals
 */
export const DataLayerInternalsContext = createContext<DataLayerInternals | null>(null);

DataLayerInternalsContext.displayName = 'DataLayerInternalsContext';

/**
 * Hook to access data layer internals (for use by other data hooks)
 *
 * @internal
 * @example
 * ```tsx
 * // Inside a data hook
 * const { database, syncCoordinator, isOnline } = useDataLayerInternals();
 * ```
 */
export const useDataLayerInternals = (): DataLayerInternals => {
  const context = useContext(DataLayerInternalsContext);
  if (!context) {
    throw new Error('useDataLayerInternals must be used within a DataLayerProvider');
  }
  return context;
};
