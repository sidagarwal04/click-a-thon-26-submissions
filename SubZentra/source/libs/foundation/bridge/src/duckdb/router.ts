/**
 * DuckDB Router - Routes queries to appropriate bridge (WASM or Native)
 * @module duckdb/router
 */

import isEqual from 'react-fast-compare';

import type { Milliseconds } from '@open-zentra/foundation-data-model';
import { Timestamp } from '@open-zentra/foundation-data-model';
import type { Logger } from '@open-zentra/foundation-utils';
import {
  createDebugLogger,
  createDeepEqualComparison,
  createSingletonFactory,
  getErrorMessage,
  Mutex,
  SafeTimer,
} from '@open-zentra/foundation-utils';

import { BRIDGE_TYPE, DEFAULTS } from '../constants';
import type { BridgeType } from '../constants';
import { EnvironmentDetector } from '../detection';
import { BridgeNotInitializedError } from '../errors/bridge-errors';
import { ElectronDuckDBBridge } from '../native/electron-bridge';
import type {
  DuckDBBridge,
  DuckDBBridgeStatus,
  QueryOptions,
  QueryResult,
  TableInfo,
  ViewDefinition,
} from '../types/bridge';
import { validateIdentifier, validateViewSql } from '../utils/sql';
import { WasmDuckDBBridge } from '../wasm/wasm-bridge';

// =============================================================================
// Types
// =============================================================================

/**
 * DuckDB Router configuration
 */
export interface DuckDBRouterConfig {
  /** Force a specific bridge type (if not set, auto-detects) */
  forceBridgeType?: BridgeType;
  /** Idle timeout before shutdown (ms). Set to 0 to disable. */
  idleTimeout?: Milliseconds;
  /** Enable debug logging */
  debug?: boolean;
  /** Enable auto-initialization */
  autoInit?: boolean;
}

/**
 * Resolved router configuration with all defaults applied
 * forceBridgeType remains optional since undefined means auto-detect
 */
interface ResolvedRouterConfig {
  /** Force a specific bridge type (undefined = auto-detect) */
  forceBridgeType: BridgeType | undefined;
  /** Idle timeout before shutdown (ms) */
  idleTimeout: Milliseconds;
  /** Enable debug logging */
  debug: boolean;
  /** Enable auto-initialization */
  autoInit: boolean;
}

/**
 * Default router configuration
 */
const DEFAULT_CONFIG: ResolvedRouterConfig = {
  forceBridgeType: undefined,
  idleTimeout: DEFAULTS.IDLE_TIMEOUT_MS,
  debug: false,
  autoInit: true,
};

// =============================================================================
// DuckDB Router Class
// =============================================================================

/**
 * DuckDB Router - Abstracts WASM vs Native DuckDB
 *
 * Features:
 * - Auto-detects best bridge type (WASM for web, Native for Electron)
 * - Lazy initialization
 * - Idle timeout with automatic shutdown
 * - View definition tracking for rehydration
 * - Transaction support
 */
export class DuckDBRouter implements DuckDBBridge {
  private readonly config: ResolvedRouterConfig;
  private readonly logger: Logger;

  private bridge: DuckDBBridge | null = null;
  private bridgeType: BridgeType | null = null;
  private idleTimer: SafeTimer | null = null;
  private lastActivityAt: Timestamp | null = null;
  private readonly viewDefinitions = new Map<string, ViewDefinition>();

  /**
   * Mutex for protecting initialization to prevent race conditions.
   * Ensures only one initialization happens even with concurrent calls.
   */
  private readonly initMutex = new Mutex();

  constructor(config: DuckDBRouterConfig = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = createDebugLogger('DuckDBRouter', this.config.debug);
  }

  // ===========================================================================
  // Private Helpers
  // ===========================================================================

  /**
   * Determine which bridge type to use
   */
  private determineBridgeType(): BridgeType {
    if (this.config.forceBridgeType) {
      return this.config.forceBridgeType;
    }

    // Auto-detect: use native if available
    if (EnvironmentDetector.hasNativeDuckDB()) {
      return BRIDGE_TYPE.NATIVE;
    }

    return BRIDGE_TYPE.WASM;
  }

  /**
   * Create the appropriate bridge
   */
  private createBridge(): DuckDBBridge {
    const type = this.determineBridgeType();
    this.bridgeType = type;

    this.logger.info('Creating bridge', { type });

    if (type === BRIDGE_TYPE.NATIVE) {
      return new ElectronDuckDBBridge({ debug: this.config.debug });
    } else {
      return new WasmDuckDBBridge({
        debug: this.config.debug,
      });
    }
  }

  /**
   * Reset idle timer using SafeTimer for automatic cleanup
   */
  private resetIdleTimer(): void {
    // Dispose existing timer
    if (this.idleTimer) {
      this.idleTimer.dispose();
      this.idleTimer = null;
    }

    this.lastActivityAt = Timestamp.now();

    if (this.config.idleTimeout > 0) {
      this.idleTimer = new SafeTimer({
        delay: this.config.idleTimeout,
        callback: () => this.handleIdleTimeout(),
        debug: this.config.debug,
        autoStart: true,
      });
    }
  }

  /**
   * Handle idle timeout
   */
  private async handleIdleTimeout(): Promise<void> {
    this.logger.info('Idle timeout reached, shutting down bridge');

    // Store view definitions before shutdown
    if (this.bridge?.isInitialized()) {
      try {
        const views = await this.bridge.getViews();
        for (const view of views) {
          this.viewDefinitions.set(view.name, view);
        }
      } catch (error) {
        this.logger.warn('Failed to save views before shutdown', {
          error: getErrorMessage(error),
        });
      }
    }

    await this.shutdown();
  }

  /**
   * Ensure bridge is ready (lazy initialization)
   *
   * Uses mutex to prevent race conditions during concurrent initialization.
   * Multiple callers will wait for the same initialization to complete.
   */
  private async ensureBridge(): Promise<DuckDBBridge> {
    this.resetIdleTimer();

    // Fast path: if already initialized, return immediately
    if (this.bridge?.isInitialized()) {
      return this.bridge;
    }

    // Use mutex to ensure only one initialization happens
    return this.initMutex.runExclusive(async () => {
      // Double-check after acquiring lock (another caller may have initialized)
      if (this.bridge?.isInitialized()) {
        return this.bridge;
      }

      // Initialize bridge
      await this.initializeBridge();

      if (!this.bridge) {
        throw new BridgeNotInitializedError('DuckDBRouter');
      }
      return this.bridge;
    });
  }

  /**
   * Initialize the bridge
   */
  private async initializeBridge(): Promise<void> {
    this.bridge = this.createBridge();
    await this.bridge.initialize();

    // Restore views if we had any - use parallel rehydration for better performance
    await this.rehydrateViewsParallel();

    this.logger.info('Bridge initialized', { type: this.bridgeType });
  }

  /**
   * Rehydrate views in parallel, respecting dependencies
   *
   * Groups views by dependency level and executes independent views in parallel.
   * Views with dependencies wait until their dependencies are created.
   */
  private async rehydrateViewsParallel(): Promise<void> {
    if (this.viewDefinitions.size === 0 || !this.bridge) {
      return;
    }
    const bridge = this.bridge;

    // Build dependency graph levels (topological sort)
    const levels = this.buildViewDependencyLevels();

    this.logger.debug('Rehydrating views', {
      totalViews: this.viewDefinitions.size,
      levels: levels.length,
    });

    // Process each level in parallel
    for (let i = 0; i < levels.length; i++) {
      const level = levels[i];

      this.logger.debug(`Processing view level ${i + 1}`, {
        viewCount: level.length,
      });

      // Create all views at this level in parallel
      const results = await Promise.allSettled(
        level.map(async (view) => {
          try {
            await bridge.createView(view);
            this.logger.debug('Restored view', { name: view.name });
            return { name: view.name, success: true };
          } catch (error) {
            this.logger.warn('Failed to restore view', {
              name: view.name,
              error: getErrorMessage(error),
            });
            return { name: view.name, success: false, error };
          }
        }),
      );

      // Log any failures at this level
      const failures = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      if (failures.length > 0) {
        this.logger.warn(`${failures.length} view(s) failed at level ${i + 1}`);
      }
    }
  }

  /**
   * Build dependency levels for views (topological sort)
   *
   * Returns an array of arrays, where each inner array contains views
   * that can be created in parallel (no dependencies on each other).
   */
  private buildViewDependencyLevels(): ViewDefinition[][] {
    const views = Array.from(this.viewDefinitions.values());

    if (views.length === 0) {
      return [];
    }

    // Create a map of view names for quick lookup
    const viewNames = new Set(views.map((v) => v.name));

    // Track which views have been assigned to a level
    const assigned = new Set<string>();
    const levels: ViewDefinition[][] = [];

    // Keep assigning views to levels until all are assigned
    while (assigned.size < views.length) {
      const currentLevel: ViewDefinition[] = [];

      for (const view of views) {
        if (assigned.has(view.name)) {
          continue;
        }

        // Check if all dependencies are satisfied
        // Dependencies are satisfied if they either:
        // 1. Are not views (they're tables that already exist)
        // 2. Have already been assigned to a previous level
        const dependenciesSatisfied = view.dependencies.every(
          (dep) => !viewNames.has(dep) || assigned.has(dep),
        );

        if (dependenciesSatisfied) {
          currentLevel.push(view);
        }
      }

      // If no views could be added, we have a circular dependency
      // In this case, just add the remaining views (best effort)
      if (currentLevel.length === 0 && assigned.size < views.length) {
        this.logger.warn('Circular dependency detected in views, adding remaining views');
        for (const view of views) {
          if (!assigned.has(view.name)) {
            currentLevel.push(view);
          }
        }
      }

      // Mark all views in this level as assigned
      for (const view of currentLevel) {
        assigned.add(view.name);
      }

      if (currentLevel.length > 0) {
        levels.push(currentLevel);
      }
    }

    return levels;
  }

  // ===========================================================================
  // DuckDBBridge Interface Implementation
  // ===========================================================================

  async initialize(): Promise<void> {
    if (this.config.autoInit) {
      await this.ensureBridge();
    }
  }

  isInitialized(): boolean {
    return this.bridge?.isInitialized() ?? false;
  }

  async shutdown(): Promise<void> {
    // Dispose idle timer
    if (this.idleTimer) {
      this.idleTimer.dispose();
      this.idleTimer = null;
    }

    if (this.bridge) {
      await this.bridge.shutdown();
      this.bridge = null;
    }

    this.logger.info('Shutdown complete');
  }

  async query<T extends Record<string, unknown> = Record<string, unknown>>(
    sql: string,
    options?: QueryOptions,
  ): Promise<QueryResult<T>> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Query', { sqlPreview: sql.slice(0, 80) });
    return bridge.query<T>(sql, options);
  }

  async execute(sql: string, options?: QueryOptions): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Execute', { sqlPreview: sql.slice(0, 80) });
    return bridge.execute(sql, options);
  }

  async registerFile(path: string, alias: string): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Register file', { path, alias });
    return bridge.registerFile(path, alias);
  }

  async unregisterFile(alias: string): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Unregister file', { alias });
    return bridge.unregisterFile(alias);
  }

  async createView(view: ViewDefinition): Promise<void> {
    // Validate view name and SQL before delegating to bridge
    validateIdentifier(view.name);
    validateViewSql(view.sql);

    const bridge = await this.ensureBridge();
    this.logger.debug('Create view', { name: view.name });

    // Store definition for rehydration
    this.viewDefinitions.set(view.name, view);

    return bridge.createView(view);
  }

  async dropView(name: string): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Drop view', { name });

    // Remove from definitions
    this.viewDefinitions.delete(name);

    return bridge.dropView(name);
  }

  async getTables(): Promise<readonly TableInfo[]> {
    const bridge = await this.ensureBridge();
    return bridge.getTables();
  }

  async getViews(): Promise<readonly ViewDefinition[]> {
    const bridge = await this.ensureBridge();
    return bridge.getViews();
  }

  async exists(name: string): Promise<boolean> {
    const bridge = await this.ensureBridge();
    return bridge.exists(name);
  }

  async exportToParquet(tableName: string, path: string): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Export to Parquet', { table: tableName, path });
    return bridge.exportToParquet(tableName, path);
  }

  async importParquet(path: string, tableName: string): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Import Parquet', { path, table: tableName });
    return bridge.importParquet(path, tableName);
  }

  // ===========================================================================
  // Transaction Support
  // ===========================================================================

  async beginTransaction(): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Begin transaction');
    return bridge.beginTransaction();
  }

  async commit(): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Commit');
    return bridge.commit();
  }

  async rollback(): Promise<void> {
    const bridge = await this.ensureBridge();
    this.logger.debug('Rollback');
    return bridge.rollback();
  }

  // ===========================================================================
  // Additional Methods
  // ===========================================================================

  /**
   * Get bridge status
   */
  getStatus(): DuckDBBridgeStatus {
    return {
      initialized: this.isInitialized(),
      busy: this.initMutex.isLocked,
      lastActivityAt: this.lastActivityAt,
      type: this.bridgeType ?? BRIDGE_TYPE.WASM,
    };
  }

  /**
   * Get current bridge type
   */
  getBridgeType(): BridgeType | null {
    return this.bridgeType;
  }

  /**
   * Get stored view definitions (for external rehydration)
   */
  getViewDefinitions(): ViewDefinition[] {
    return Array.from(this.viewDefinitions.values());
  }

  /**
   * Force rehydration (recreate views)
   *
   * Uses parallel processing for independent views to improve performance.
   */
  async rehydrate(): Promise<void> {
    await this.ensureBridge();
    await this.rehydrateViewsParallel();
    this.logger.info('Rehydration complete');
  }
}

// =============================================================================
// Singleton Factory
// =============================================================================

/**
 * Create DuckDB router instance
 */
export const createDuckDBRouter = (config?: DuckDBRouterConfig): DuckDBRouter =>
  new DuckDBRouter(config);

/**
 * Singleton factory for DuckDB router
 */
const routerFactory = createSingletonFactory(
  (config: DuckDBRouterConfig | undefined) => createDuckDBRouter(config),
  {
    name: 'DuckDBRouter',
    compareConfig: createDeepEqualComparison(isEqual, 'DuckDBRouter'),
    onDispose: async (instance) => {
      if (instance instanceof DuckDBRouter) {
        await instance.shutdown();
      }
    },
  },
);

/**
 * Get or create singleton router instance
 *
 * Note: If an instance already exists, the config parameter is ignored.
 * Call resetDuckDBRouter() first to change configuration.
 */
export const getDuckDBRouter = (config?: DuckDBRouterConfig): DuckDBRouter =>
  routerFactory.getInstance(config);

/**
 * Reset router instance (for testing or config change)
 */
export const resetDuckDBRouter = async (): Promise<void> => {
  await routerFactory.reset();
};

/**
 * Check if router instance exists
 */
export const hasDuckDBRouter = (): boolean => routerFactory.hasInstance();
