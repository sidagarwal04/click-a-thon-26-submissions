/**
 * Dependency Injection Container / Factory for Sync Engine
 * @module core/container
 */

import { getDatabase } from '@open-zentra/foundation-database';
import {
  CompositeDisposable,
  createDebugLogger,
  normalizeError,
  type IAsyncDisposable,
} from '@open-zentra/foundation-utils';

import { ConflictResolver } from '../conflicts/resolver';
import { SyncCoordinator } from '../coordinator';
import { CrossTabManager } from '../cross-tab/manager';
import { NetworkStatusMonitor } from '../network/index';
import { OfflineQueueManager } from '../queue/manager';
import { DEFAULT_CONFLICT_STRATEGY } from './defaults';
import type {
  IConflictResolver,
  ICrossTabManager,
  INetworkMonitor,
  IQueueManager,
  ISyncCoordinator,
  ISyncEngineFactory,
  SyncEngineConfig,
} from './interfaces';

/**
 * Container configuration
 */
export interface SyncEngineContainerConfig extends SyncEngineConfig {
  /** Custom factory implementations */
  factories?: {
    networkMonitor?: (config: SyncEngineConfig) => INetworkMonitor;
    queueManager?: (config: SyncEngineConfig) => IQueueManager;
    conflictResolver?: (config: SyncEngineConfig) => IConflictResolver;
    crossTabManager?: (config: SyncEngineConfig) => ICrossTabManager;
  };
  /** Error callback for centralized error handling */
  onError?: (error: Error, context?: string) => void;
}

/**
 * Typed component registry for the container
 * Provides type-safe access to registered components
 */
interface ComponentRegistry {
  networkMonitor?: INetworkMonitor;
  queueManager?: IQueueManager;
  conflictResolver?: IConflictResolver;
  crossTabManager?: ICrossTabManager;
  syncCoordinator?: ISyncCoordinator;
}

/**
 * Component registry keys for type-safe access
 */
type ComponentKey = keyof ComponentRegistry;

const isAsyncDisposable = (value: unknown): value is IAsyncDisposable =>
  value !== null &&
  typeof value === 'object' &&
  'disposeAsync' in value &&
  typeof value.disposeAsync === 'function';

/**
 * Type guard to check if a value implements INetworkMonitor
 */
const isNetworkMonitor = (value: unknown): value is INetworkMonitor =>
  value !== null &&
  typeof value === 'object' &&
  'isOnline' in value &&
  'start' in value &&
  'stop' in value &&
  'subscribe' in value &&
  'checkConnectivity' in value;

/**
 * Type guard to check if a value implements IQueueManager
 */
const isQueueManager = (value: unknown): value is IQueueManager =>
  value !== null &&
  typeof value === 'object' &&
  'enqueue' in value &&
  'getPendingMutations' in value &&
  'markCompleted' in value &&
  'getStats' in value;

/**
 * Type guard to check if a value implements IConflictResolver
 */
const isConflictResolver = (value: unknown): value is IConflictResolver =>
  value !== null &&
  typeof value === 'object' &&
  'resolve' in value &&
  'hasConflict' in value &&
  'getStrategy' in value;

/**
 * Type guard to check if a value implements ICrossTabManager
 */
const isCrossTabManager = (value: unknown): value is ICrossTabManager =>
  value !== null &&
  typeof value === 'object' &&
  'id' in value &&
  'isLeader' in value &&
  'broadcast' in value &&
  'subscribe' in value;

/**
 * Type guard to check if a value implements ISyncCoordinator
 */
const isSyncCoordinator = (value: unknown): value is ISyncCoordinator =>
  value !== null &&
  typeof value === 'object' &&
  'getState' in value &&
  'start' in value &&
  'stop' in value &&
  'sync' in value &&
  'subscribe' in value;

/**
 * Default factory functions
 */
const defaultFactories = {
  networkMonitor: (config: SyncEngineConfig): INetworkMonitor => {
    return new NetworkStatusMonitor({
      database: config.database,
      healthCheckUrl: config.healthCheckUrl,
      healthCheckInterval: config.healthCheckInterval,
      axiosInstance: config.axiosInstance,
      debug: config.debug,
    });
  },

  queueManager: (config: SyncEngineConfig): IQueueManager => {
    return new OfflineQueueManager({
      database: config.database,
      debug: config.debug,
    });
  },

  conflictResolver: (config: SyncEngineConfig): IConflictResolver => {
    return new ConflictResolver({
      defaultStrategy: config.conflictStrategy ?? DEFAULT_CONFLICT_STRATEGY,
      debug: config.debug,
    });
  },

  crossTabManager: (config: SyncEngineConfig): ICrossTabManager => {
    return new CrossTabManager({
      debug: config.debug,
    });
  },
};

/**
 * Sync Engine Container - Manages component lifecycle and dependencies
 * Uses typed component registry for type-safe access to instances
 */
export class SyncEngineContainer implements IAsyncDisposable {
  private config: SyncEngineContainerConfig;
  private registry: ComponentRegistry = {};
  private disposables = new CompositeDisposable();
  private registeredDisposableKeys = new Set<ComponentKey>();
  private _isDisposed = false;
  private logger;

  constructor(config: SyncEngineContainerConfig) {
    this.config = {
      ...config,
      database: config.database ?? getDatabase(),
    };
    this.logger = createDebugLogger('SyncEngineContainer', this.config.debug ?? false);
  }

  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Handle errors with optional callback
   */
  private handleError(error: unknown, context?: string): void {
    const err = normalizeError(error);
    this.logger.error(`Error in ${context ?? 'unknown'}:`, err);
    this.config.onError?.(err, context);
  }

  /**
   * Get or create network monitor with type validation
   */
  getNetworkMonitor(): INetworkMonitor {
    this.ensureNotDisposed();

    const key: ComponentKey = 'networkMonitor';
    if (!this.registry[key]) {
      const factory = this.config.factories?.networkMonitor;
      const instance = factory
        ? factory(this.config)
        : defaultFactories.networkMonitor(this.config);

      // Validate instance type at runtime
      if (!isNetworkMonitor(instance)) {
        throw new Error('Factory returned invalid INetworkMonitor implementation');
      }

      this.registry[key] = instance;

      // Register disposal only once (idempotent)
      if (!this.registeredDisposableKeys.has(key)) {
        this.registeredDisposableKeys.add(key);
        this.disposables.addFunction(() => {
          const monitor = this.registry[key];
          if (isAsyncDisposable(monitor)) {
            monitor.disposeAsync().catch((err) => {
              this.handleError(err, 'NetworkMonitor disposal');
            });
          }
        });
      }
    }

    return this.registry[key]!;
  }

  /**
   * Get or create queue manager with type validation
   */
  getQueueManager(): IQueueManager {
    this.ensureNotDisposed();

    const key: ComponentKey = 'queueManager';
    if (!this.registry[key]) {
      const factory = this.config.factories?.queueManager;
      const instance = factory ? factory(this.config) : defaultFactories.queueManager(this.config);

      // Validate instance type at runtime
      if (!isQueueManager(instance)) {
        throw new Error('Factory returned invalid IQueueManager implementation');
      }

      this.registry[key] = instance;

      // Register disposal only once (idempotent)
      if (!this.registeredDisposableKeys.has(key)) {
        this.registeredDisposableKeys.add(key);
        this.disposables.add(instance);
      }
    }

    return this.registry[key]!;
  }

  /**
   * Get or create conflict resolver with type validation
   */
  getConflictResolver(): IConflictResolver {
    this.ensureNotDisposed();

    const key: ComponentKey = 'conflictResolver';
    if (!this.registry[key]) {
      const factory = this.config.factories?.conflictResolver;
      const instance = factory
        ? factory(this.config)
        : defaultFactories.conflictResolver(this.config);

      // Validate instance type at runtime
      if (!isConflictResolver(instance)) {
        throw new Error('Factory returned invalid IConflictResolver implementation');
      }

      this.registry[key] = instance;

      // Register disposal only once (idempotent)
      if (!this.registeredDisposableKeys.has(key)) {
        this.registeredDisposableKeys.add(key);
        this.disposables.add(instance);
      }
    }

    return this.registry[key]!;
  }

  /**
   * Get or create cross-tab manager with type validation
   */
  getCrossTabManager(): ICrossTabManager | null {
    this.ensureNotDisposed();

    if (!this.config.enableCrossTab) {
      return null;
    }

    const key: ComponentKey = 'crossTabManager';
    if (!this.registry[key]) {
      const factory = this.config.factories?.crossTabManager;
      const instance = factory
        ? factory(this.config)
        : defaultFactories.crossTabManager(this.config);

      // Validate instance type at runtime
      if (!isCrossTabManager(instance)) {
        throw new Error('Factory returned invalid ICrossTabManager implementation');
      }

      this.registry[key] = instance;

      // Register disposal only once (idempotent)
      if (!this.registeredDisposableKeys.has(key)) {
        this.registeredDisposableKeys.add(key);
        this.disposables.add(instance);
      }
    }

    return this.registry[key]!;
  }

  /**
   * Get or create sync coordinator with type validation
   */
  getSyncCoordinator(): ISyncCoordinator {
    this.ensureNotDisposed();

    const key: ComponentKey = 'syncCoordinator';
    if (!this.registry[key]) {
      const instance = new SyncCoordinator({
        ...this.config,
        autoStart: false, // We'll manage lifecycle
      });

      // Validate instance type at runtime
      if (!isSyncCoordinator(instance)) {
        throw new Error('Created invalid ISyncCoordinator implementation');
      }

      this.registry[key] = instance;
      // Note: SyncCoordinator disposal is handled separately in disposeAsync
    }

    return this.registry[key]!;
  }

  /**
   * Start all services
   */
  async start(): Promise<void> {
    this.ensureNotDisposed();

    try {
      const networkMonitor = this.getNetworkMonitor();
      await networkMonitor.start();

      const crossTabManager = this.getCrossTabManager();
      crossTabManager?.start();

      if (this.config.autoStart !== false) {
        const coordinator = this.getSyncCoordinator();
        await coordinator.start();
      }
    } catch (error) {
      this.handleError(error, 'Container start');
      throw error;
    }
  }

  /**
   * Stop all services
   */
  stop(): void {
    try {
      this.registry.syncCoordinator?.stop();
      this.registry.crossTabManager?.stop();
      this.registry.networkMonitor?.stop();
    } catch (error) {
      this.handleError(error, 'Container stop');
    }
  }

  /**
   * Async dispose - properly awaits all async disposables
   */
  async disposeAsync(): Promise<void> {
    if (this._isDisposed) return;
    this._isDisposed = true;

    this.stop();

    // Dispose coordinator with proper awaiting
    if (this.registry.syncCoordinator) {
      try {
        await this.registry.syncCoordinator.disposeAsync();
      } catch (error) {
        this.handleError(error, 'SyncCoordinator async disposal');
      }
    }

    // Dispose network monitor with proper awaiting
    if (isAsyncDisposable(this.registry.networkMonitor)) {
      try {
        await this.registry.networkMonitor.disposeAsync();
      } catch (error) {
        this.handleError(error, 'NetworkMonitor async disposal');
      }
    }

    // Dispose sync disposables
    this.disposables.dispose();
    this.registry = {};
    this.registeredDisposableKeys.clear();

    this.logger.debug('Container disposed');
  }

  private ensureNotDisposed(): void {
    if (this._isDisposed) {
      throw new Error('SyncEngineContainer has been disposed');
    }
  }
}

/**
 * Sync Engine Factory implementation
 */
export class SyncEngineFactory implements ISyncEngineFactory {
  private containers: Map<string, SyncEngineContainer> = new Map();
  private defaultConfig: Partial<SyncEngineConfig> = {};

  /**
   * Set default configuration
   */
  setDefaults(config: Partial<SyncEngineConfig>): void {
    this.defaultConfig = { ...this.defaultConfig, ...config };
  }

  /**
   * Create a new container with scoped instances
   */
  createContainer(config: SyncEngineContainerConfig): SyncEngineContainer {
    const finalConfig = { ...this.defaultConfig, ...config };
    return new SyncEngineContainer(finalConfig);
  }

  /**
   * Create a sync coordinator
   */
  createCoordinator(config: SyncEngineConfig): ISyncCoordinator {
    return new SyncCoordinator(config);
  }

  /**
   * Create a network monitor
   */
  createNetworkMonitor(config?: Partial<SyncEngineConfig>): INetworkMonitor {
    return new NetworkStatusMonitor({
      database: config?.database,
      healthCheckUrl: config?.healthCheckUrl,
      healthCheckInterval: config?.healthCheckInterval,
      axiosInstance: config?.axiosInstance,
      debug: config?.debug,
    });
  }

  /**
   * Create a queue manager
   */
  createQueueManager(config?: Partial<SyncEngineConfig>): IQueueManager {
    return new OfflineQueueManager({
      database: config?.database,
      debug: config?.debug,
    });
  }

  /**
   * Create a conflict resolver
   */
  createConflictResolver(config?: Partial<SyncEngineConfig>): IConflictResolver {
    return new ConflictResolver({
      defaultStrategy: config?.conflictStrategy ?? DEFAULT_CONFLICT_STRATEGY,
      debug: config?.debug,
    });
  }

  /**
   * Create a cross-tab manager
   */
  createCrossTabManager(config?: Partial<SyncEngineConfig>): ICrossTabManager {
    return new CrossTabManager({
      debug: config?.debug,
    });
  }

  /**
   * Get or create a named container
   */
  getContainer(name: string, config?: SyncEngineContainerConfig): SyncEngineContainer {
    if (!this.containers.has(name)) {
      if (!config) {
        throw new Error(`Container "${name}" not found. Provide config to create.`);
      }
      const newContainer = this.createContainer(config);
      this.containers.set(name, newContainer);
    }
    return this.containers.get(name)!;
  }

  /**
   * Dispose a named container asynchronously
   */
  async disposeContainerAsync(name: string): Promise<void> {
    const container = this.containers.get(name);
    if (container) {
      await container.disposeAsync();
      this.containers.delete(name);
    }
  }

  /**
   * Dispose all containers asynchronously
   */
  async disposeAllAsync(): Promise<void> {
    const disposalPromises: Promise<void>[] = [];
    for (const container of this.containers.values()) {
      disposalPromises.push(container.disposeAsync());
    }
    await Promise.all(disposalPromises);
    this.containers.clear();
  }
}

/**
 * Default factory instance
 */
export const syncEngineFactory = new SyncEngineFactory();

/**
 * Create a scoped container for the sync engine
 */
export const createSyncEngineContainer = (
  config: SyncEngineContainerConfig,
): SyncEngineContainer => {
  return new SyncEngineContainer(config);
};
