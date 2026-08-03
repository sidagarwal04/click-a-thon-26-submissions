/**
 * Data Layer Container
 *
 * Centralized dependency injection container for the data layer.
 *
 * @module core/container
 */

import { QueryClient } from '@tanstack/react-query';
import type { AxiosInstance } from 'axios';

import { DuckDBRouter } from '@open-zentra/foundation-bridge';
import {
  CONFLICT_STRATEGY,
  type ApiMutationDescriptor,
  type ApiQueryDescriptor,
  type ConflictStrategy,
  type UnifiedTableConfig as SharedUnifiedTableConfig,
} from '@open-zentra/foundation-data-model';
import { DatabaseFacade, OpfsManager } from '@open-zentra/foundation-database';
import {
  createSyncCoordinator,
  type SyncCoordinator,
} from '@open-zentra/foundation-sync-engine';
import { createLogger, Mutex, type Logger } from '@open-zentra/foundation-utils';

import { FileDownloadService } from '../analytics-sync/file-download-service';
import { TableSyncService } from '../analytics-sync/table-sync-service';
import { RealtimeSocketClient } from '../realtime';
import { pickDefined } from './config-normalization';
import {
  OFFLINE_NETWORK_MODE,
  QUERY_RETRY_DELAY_BASE_MS,
  QUERY_RETRY_DELAY_MAX_MS,
  QUERY_RETRY_MAX,
  resolveCacheConfig,
} from './constants';
import { createTableRegistry, type TableRegistry } from './table-registry';
import type {
  CacheConfig,
  DataSourceEndpointDescriptor,
  RealtimeSocketConfig,
  ResolvedCacheConfig,
} from './types';

type UnifiedTableConfig = SharedUnifiedTableConfig<ApiQueryDescriptor, ApiMutationDescriptor>;

export interface DataLayerDependencies {
  readonly database: DatabaseFacade;
  readonly syncCoordinator: SyncCoordinator;
  readonly duckdbRouter: DuckDBRouter | null;
  readonly opfsManager: OpfsManager | null;
  readonly analyticsEnabled: boolean;
  readonly initializeAnalytics: () => Promise<{
    readonly duckdbRouter: DuckDBRouter;
    readonly opfsManager: OpfsManager | null;
  } | null>;
  readonly queryClient: QueryClient;
  readonly axiosInstance: AxiosInstance;
  readonly realtimeClient: RealtimeSocketClient;
  readonly cacheConfig: ResolvedCacheConfig;
  readonly tableRegistry: TableRegistry;
  readonly datasourceEndpoint: DataSourceEndpointDescriptor | null;
  readonly getTableSyncService: () => TableSyncService;
  readonly getFileDownloadService: () => Promise<FileDownloadService | null>;
}

export interface DependencyFactories {
  readonly database: () => DatabaseFacade;
  readonly syncCoordinator: (config: {
    queryClient: QueryClient;
    tables?: ReadonlyArray<UnifiedTableConfig>;
    database: DatabaseFacade;
    conflictStrategy: ConflictStrategy;
    enableCrossTab: boolean;
    autoStart: boolean;
    debug: boolean;
    axiosInstance: AxiosInstance;
    onError?: (error: Error, context?: string) => void;
  }) => SyncCoordinator;
  readonly duckdbRouter: () => DuckDBRouter;
  readonly opfsManager: (database: DatabaseFacade) => OpfsManager;
  readonly realtimeClient: (
    config: RealtimeSocketConfig,
    deps: {
      readonly axiosInstance: AxiosInstance;
      readonly database: DatabaseFacade;
      readonly debug?: boolean;
    },
  ) => RealtimeSocketClient;
}

export interface ContainerConfig {
  readonly tables?: ReadonlyArray<UnifiedTableConfig>;
  readonly datasourceEndpoint?: DataSourceEndpointDescriptor;
  readonly conflictStrategy?: ConflictStrategy;
  readonly enableCrossTab?: boolean;
  readonly enableAnalytics?: boolean;
  readonly defaultStaleTime?: number;
  readonly defaultGcTime?: number;
  readonly cache?: CacheConfig;
  readonly axiosInstance: AxiosInstance;
  readonly websocket: RealtimeSocketConfig;
  readonly debug?: boolean;
  readonly onSyncError?: (error: Error, context?: string) => void;
  readonly factories?: Partial<DependencyFactories>;
}

export class DataLayerContainer {
  private deps: DataLayerDependencies | null = null;
  private disposed = false;
  private initPromise: Promise<DataLayerDependencies> | null = null;
  private readonly disposeMutex = new Mutex();
  private readonly analyticsInitMutex = new Mutex();
  private analyticsRuntime: {
    readonly duckdbRouter: DuckDBRouter;
    readonly opfsManager: OpfsManager | null;
  } | null = null;
  private tableSyncService: TableSyncService | null = null;
  private fileDownloadService: FileDownloadService | null = null;
  private fileDownloadServiceOpfsManager: OpfsManager | null = null;
  private readonly config: ContainerConfig;
  private readonly logger: Logger;

  constructor(config: ContainerConfig) {
    this.config = config;
    this.logger = createLogger('DataLayerContainer', { level: config.debug ? 'debug' : 'warn' });
  }

  private log = (message: string, ...args: unknown[]): void => {
    this.logger.debug(message, ...args);
  };

  initialize = async (): Promise<DataLayerDependencies> => {
    if (this.disposed) {
      throw new Error('[DataLayerContainer] Container is disposed');
    }

    if (this.deps) {
      return this.deps;
    }

    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = this.doInitialize();

    try {
      const deps = await this.initPromise;
      this.deps = deps;
      return deps;
    } finally {
      this.initPromise = null;
    }
  };

  private doInitialize = async (): Promise<DataLayerDependencies> => {
    this.log('Initializing container');

    const cacheConfig = resolveCacheConfig({
      ...this.config.cache,
      defaultStaleTime: this.config.defaultStaleTime ?? this.config.cache?.defaultStaleTime,
      defaultGcTime: this.config.defaultGcTime ?? this.config.cache?.defaultGcTime,
    });

    const tableRegistry = createTableRegistry(this.config.tables ?? [], {
      staleTime: cacheConfig.defaultStaleTime,
      gcTime: cacheConfig.defaultGcTime,
      conflictStrategy: this.config.conflictStrategy ?? CONFLICT_STRATEGY.LAST_WRITE_WINS,
      ...pickDefined({
        debug: this.config.debug,
      }),
    });

    const queryClient = this.createQueryClient(cacheConfig);

    const databaseConfig =
      this.config.debug === undefined ? undefined : { debug: this.config.debug };
    const database = this.config.factories?.database?.() ?? DatabaseFacade.create(databaseConfig);

    const syncCoordinator =
      this.config.factories?.syncCoordinator?.({
        queryClient,
        tables: this.config.tables,
        database,
        conflictStrategy: this.config.conflictStrategy ?? CONFLICT_STRATEGY.LAST_WRITE_WINS,
        enableCrossTab: this.config.enableCrossTab ?? true,
        autoStart: true,
        debug: this.config.debug ?? false,
        axiosInstance: this.config.axiosInstance,
        onError: this.config.onSyncError,
      }) ??
      createSyncCoordinator({
        queryClient,
        tables: this.config.tables,
        database: database.getDatabase(),
        conflictStrategy: this.config.conflictStrategy ?? CONFLICT_STRATEGY.LAST_WRITE_WINS,
        enableCrossTab: this.config.enableCrossTab ?? true,
        autoStart: true,
        axiosInstance: this.config.axiosInstance,
        debug: this.config.debug,
        onError: this.config.onSyncError,
      });

    const realtimeClient =
      this.config.factories?.realtimeClient?.(this.config.websocket, {
        axiosInstance: this.config.axiosInstance,
        database,
        debug: this.config.debug,
      }) ??
      new RealtimeSocketClient(this.config.websocket, {
        axiosInstance: this.config.axiosInstance,
        syncState: database.syncState,
        debug: this.config.debug,
      });

    database.startCleanup();

    return {
      database,
      syncCoordinator,
      duckdbRouter: null,
      opfsManager: null,
      analyticsEnabled: this.config.enableAnalytics !== false,
      initializeAnalytics: () => this.ensureAnalyticsRuntime(database),
      queryClient,
      axiosInstance: this.config.axiosInstance,
      realtimeClient,
      cacheConfig,
      tableRegistry,
      datasourceEndpoint: this.config.datasourceEndpoint ?? null,
      getTableSyncService: () => this.getOrCreateTableSyncService(database),
      getFileDownloadService: () => this.getOrCreateFileDownloadService(database),
    };
  };

  private getOrCreateTableSyncService = (database: DatabaseFacade): TableSyncService => {
    if (!this.tableSyncService) {
      this.tableSyncService = new TableSyncService({
        axiosInstance: this.config.axiosInstance,
        datasourceEndpoint: this.config.datasourceEndpoint ?? null,
        database: database.tableSyncMetadata,
        ...pickDefined({
          debug: this.config.debug,
        }),
      });
    }

    return this.tableSyncService;
  };

  private getOrCreateFileDownloadService = async (
    database: DatabaseFacade,
  ): Promise<FileDownloadService | null> => {
    const runtime = await this.ensureAnalyticsRuntime(database);
    const runtimeOpfsManager = runtime?.opfsManager ?? null;
    if (!runtimeOpfsManager) {
      return null;
    }

    if (!this.fileDownloadService || this.fileDownloadServiceOpfsManager !== runtimeOpfsManager) {
      this.fileDownloadService = new FileDownloadService({
        opfsManager: runtimeOpfsManager,
        axiosInstance: this.config.axiosInstance,
        ...pickDefined({
          debug: this.config.debug,
        }),
      });
      this.fileDownloadServiceOpfsManager = runtimeOpfsManager;
    }

    return this.fileDownloadService;
  };

  private ensureAnalyticsRuntime = async (
    database: DatabaseFacade,
  ): Promise<{
    readonly duckdbRouter: DuckDBRouter;
    readonly opfsManager: OpfsManager | null;
  } | null> => {
    if (this.config.enableAnalytics === false) {
      return null;
    }

    if (this.analyticsRuntime) {
      return this.analyticsRuntime;
    }

    return this.analyticsInitMutex.runExclusive(async () => {
      if (this.analyticsRuntime) {
        return this.analyticsRuntime;
      }

      try {
        const duckdbRouter =
          this.config.factories?.duckdbRouter?.() ??
          new DuckDBRouter(
            pickDefined({
              debug: this.config.debug,
            }),
          );
        const opfsManager =
          this.config.factories?.opfsManager?.(database) ??
          new OpfsManager({
            database: database.getDatabase(),
            ...pickDefined({
              debug: this.config.debug,
            }),
          });

        this.analyticsRuntime = { duckdbRouter, opfsManager };
        this.log('Analytics runtime initialized lazily');

        return this.analyticsRuntime;
      } catch (error) {
        this.logger.warn('Analytics runtime unavailable', error);
        return null;
      }
    });
  };

  private createQueryClient = (cacheConfig: ResolvedCacheConfig): QueryClient =>
    new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: cacheConfig.defaultStaleTime,
          gcTime: cacheConfig.defaultGcTime,
          retry: QUERY_RETRY_MAX,
          retryDelay: (attempt) =>
            Math.min(QUERY_RETRY_DELAY_BASE_MS * Math.pow(2, attempt), QUERY_RETRY_DELAY_MAX_MS),
          networkMode: OFFLINE_NETWORK_MODE,
          refetchOnWindowFocus: false,
          refetchOnReconnect: true,
        },
        mutations: {
          retry: QUERY_RETRY_MAX,
          networkMode: OFFLINE_NETWORK_MODE,
        },
      },
    });

  dispose = async (): Promise<void> => {
    const release = await this.disposeMutex.acquire();
    try {
      if (this.disposed) {
        return;
      }

      if (this.initPromise) {
        try {
          await this.initPromise;
        } catch {
          // Ignore initialization failures during disposal
        }
      }

      if (!this.deps) {
        this.disposed = true;
        return;
      }

      const { syncCoordinator, database, realtimeClient } = this.deps;

      try {
        await syncCoordinator.disposeAsync();
      } catch (error) {
        this.logger.error('Error disposing sync coordinator:', error);
      }

      if (this.analyticsRuntime?.duckdbRouter) {
        try {
          await this.analyticsRuntime.duckdbRouter.shutdown();
        } catch (error) {
          this.logger.error('Error shutting down DuckDB router:', error);
        }
      }

      if (this.analyticsRuntime?.opfsManager) {
        try {
          await this.analyticsRuntime.opfsManager.dispose();
        } catch (error) {
          this.logger.error('Error disposing OPFS manager:', error);
        }
      }

      try {
        database.stopCleanup();
        database.close();
      } catch (error) {
        this.logger.error('Error closing database:', error);
      }

      try {
        realtimeClient.disconnect();
      } catch (error) {
        this.logger.error('Error closing realtime client:', error);
      }

      this.analyticsRuntime = null;
      this.tableSyncService = null;
      this.fileDownloadService = null;
      this.fileDownloadServiceOpfsManager = null;
      this.deps = null;
      this.disposed = true;
    } finally {
      release();
    }
  };

  get isDisposed(): boolean {
    return this.disposed;
  }

  getDependencies = (): DataLayerDependencies => {
    if (this.disposed) {
      throw new Error('[DataLayerContainer] Container is disposed');
    }
    if (!this.deps) {
      throw new Error('[DataLayerContainer] Container not initialized');
    }
    return this.deps;
  };

  get isInitialized(): boolean {
    return this.deps !== null && !this.disposed;
  }
}

export const createDataLayerContainer = (config: ContainerConfig): DataLayerContainer =>
  new DataLayerContainer(config);
