/**
 * Unified Table Registry
 *
 * Single source of truth for table metadata used across:
 * - DataLayer (HTTP API calls, caching)
 * - SyncEngine (conflict resolution, offline sync)
 * - QueryEngine (routing decisions, analytics)
 *
 * Tables are defined ONCE in DataLayerConfig and accessed via this registry.
 *
 * @module core/table-registry
 */

import {
  type ApiMutationDescriptor,
  type ApiQueryDescriptor,
  CONFLICT_STRATEGY,
  DATA_FRESHNESS,
  type ConflictStrategy,
  type DataFreshnessLevel,
  type Operation,
  type UnifiedTableConfig as SharedUnifiedTableConfig,
} from '@open-zentra/foundation-data-model';
import { createDebugLogger, TIME_MS, type Logger } from '@open-zentra/foundation-utils';

type UnifiedTableConfig = SharedUnifiedTableConfig<
  ApiQueryDescriptor,
  ApiMutationDescriptor
>;

// =============================================================================
// TABLE REGISTRY
// =============================================================================

/**
 * TableRegistry - centralized access to table configurations.
 *
 * Provides typed accessors for different use cases:
 * - DataLayer hooks: getApiDescriptor, getStaleTime
 * - SyncEngine: getConflictStrategy, getMergeConfig
 * - QueryEngine: isAnalyticsEnabled, getAnalyticsFreshness
 */
export class TableRegistry {
  private readonly tables = new Map<string, UnifiedTableConfig>();
  private readonly defaults: {
    readonly staleTime: number;
    readonly gcTime: number;
    readonly conflictStrategy: ConflictStrategy;
  };
  private readonly logger: Logger;

  constructor(
    tables: ReadonlyArray<UnifiedTableConfig> = [],
    defaults: {
      staleTime?: number;
      gcTime?: number;
      conflictStrategy?: ConflictStrategy;
      debug?: boolean;
    } = {},
  ) {
    this.logger = createDebugLogger('TableRegistry', defaults.debug ?? false);
    this.defaults = {
      staleTime: defaults.staleTime ?? TIME_MS.MINUTE * 5,
      gcTime: defaults.gcTime ?? TIME_MS.DAY,
      conflictStrategy: defaults.conflictStrategy ?? CONFLICT_STRATEGY.LAST_WRITE_WINS,
    };

    // Check for duplicate table names in initialization
    const seenNames = new Set<string>();
    for (const table of tables) {
      if (seenNames.has(table.name)) {
        this.logger.warn(
          `Duplicate table name '${table.name}' in initialization.`,
          'Only the last configuration will be used.',
        );
      }
      seenNames.add(table.name);
      this.tables.set(table.name, table);
    }
  }

  // ─── BASIC ACCESSORS ────────────────────────────────────────────────────────

  /**
   * Get table configuration by name.
   * Returns undefined if table not registered.
   */
  getTable = (name: string): UnifiedTableConfig | undefined => this.tables.get(name);

  /**
   * Get table configuration by name, throwing if not found.
   */
  getTableOrThrow = (name: string): UnifiedTableConfig => {
    const table = this.tables.get(name);
    if (!table) {
      throw new Error(`[TableRegistry] Table '${name}' not registered`);
    }
    return table;
  };

  /**
   * Check if table is registered.
   */
  hasTable = (name: string): boolean => this.tables.has(name);

  /**
   * Get all registered tables.
   */
  getAllTables = (): ReadonlyArray<UnifiedTableConfig> => Array.from(this.tables.values());

  /**
   * Get all registered table names.
   */
  getTableNames = (): ReadonlyArray<string> => Array.from(this.tables.keys());

  /**
   * Register a new table (for dynamic registration).
   *
   * Warns if overwriting an existing table configuration.
   * Use `forceRegister` to suppress the warning.
   *
   * @param config - Table configuration to register
   * @param options - Registration options
   * @param options.force - If true, suppress warning when overwriting
   *
   * @example
   * ```typescript
   * // Register new table
   * registry.registerTable({ name: 'users', ... });
   *
   * // Overwrites with warning
   * registry.registerTable({ name: 'users', ... }); // logs warning
   *
   * // Force overwrite without warning
   * registry.registerTable({ name: 'users', ... }, { force: true });
   * ```
   */
  registerTable = (config: UnifiedTableConfig, options?: { force?: boolean }): void => {
    const existing = this.tables.get(config.name);

    if (existing && !options?.force) {
      this.logger.warn(
        `Overwriting existing table configuration for '${config.name}'.`,
        'Use { force: true } to suppress this warning.',
      );
    }

    this.tables.set(config.name, config);
  };

  /**
   * Unregister a table.
   *
   * @param name - Table name to unregister
   * @returns true if the table was removed, false if it didn't exist
   */
  unregisterTable = (name: string): boolean => this.tables.delete(name);

  // ─── API ACCESSORS (DataLayer, QueryEngine) ─────────────────────────────────

  /**
   * Get API descriptor for a table and operation.
   * Returns undefined if not defined.
   */
  getApiDescriptor = (
    tableName: string,
    operation: Operation,
  ): ApiQueryDescriptor | ApiMutationDescriptor | undefined => {
    const table = this.tables.get(tableName);
    return table?.api?.[operation];
  };

  /**
   * Get mutation descriptors for a table (create, update, delete).
   * Used by DataLayer hooks and SyncEngine.
   */
  getMutationDescriptors = (
    tableName: string,
  ): {
    create?: ApiMutationDescriptor;
    update?: ApiMutationDescriptor;
    delete?: ApiMutationDescriptor;
  } => {
    const table = this.tables.get(tableName);
    const refs: {
      create?: ApiMutationDescriptor;
      update?: ApiMutationDescriptor;
      delete?: ApiMutationDescriptor;
    } = {};
    if (table?.api?.create) {
      refs.create = table.api.create;
    }
    if (table?.api?.update) {
      refs.update = table.api.update;
    }
    if (table?.api?.delete) {
      refs.delete = table.api.delete;
    }
    return refs;
  };

  /**
   * Check if table has a specific API operation defined.
   */
  hasApiDescriptor = (tableName: string, operation: Operation): boolean =>
    this.getApiDescriptor(tableName, operation) !== undefined;

  // ─── CACHE ACCESSORS (DataLayer, QueryEngine) ───────────────────────────────

  /**
   * Get stale time for a table (with default fallback).
   */
  getStaleTime = (tableName: string): number => {
    const table = this.tables.get(tableName);
    return table?.staleTime ?? this.defaults.staleTime;
  };

  /**
   * Get GC time for a table (with default fallback).
   */
  getGcTime = (tableName: string): number => {
    const table = this.tables.get(tableName);
    return table?.gcTime ?? this.defaults.gcTime;
  };

  // ─── CONFLICT ACCESSORS (SyncEngine) ────────────────────────────────────────

  /**
   * Get conflict resolution strategy for a table.
   */
  getConflictStrategy = (tableName: string): ConflictStrategy => {
    const table = this.tables.get(tableName);
    return table?.conflictStrategy ?? this.defaults.conflictStrategy;
  };

  /**
   * Get merge configuration for a table (for 'merge' strategy).
   */
  getMergeConfig = (tableName: string): UnifiedTableConfig['mergeConfig'] | undefined => {
    const table = this.tables.get(tableName);
    return table?.mergeConfig;
  };

  /**
   * Get all table conflict strategies (for SyncEngine initialization).
   */
  getTableStrategies = (): Record<string, ConflictStrategy> => {
    const strategies: Record<string, ConflictStrategy> = {};
    for (const [name, table] of this.tables) {
      if (table.conflictStrategy) {
        strategies[name] = table.conflictStrategy;
      }
    }
    return strategies;
  };

  /**
   * Get all table merge configs (for SyncEngine initialization).
   */
  getTableMergeConfigs = (): Record<string, UnifiedTableConfig['mergeConfig']> => {
    const configs: Record<string, UnifiedTableConfig['mergeConfig']> = {};
    for (const [name, table] of this.tables) {
      if (table.mergeConfig) {
        configs[name] = table.mergeConfig;
      }
    }
    return configs;
  };

  // ─── ANALYTICS ACCESSORS (QueryEngine) ──────────────────────────────────────

  /**
   * Check if analytics (DuckDB) is enabled for a table.
   */
  isAnalyticsEnabled = (tableName: string): boolean => {
    const table = this.tables.get(tableName);
    return table?.analytics?.enabled ?? false;
  };

  /**
   * Get analytics freshness requirement for a table.
   */
  getAnalyticsFreshness = (tableName: string): DataFreshnessLevel => {
    const table = this.tables.get(tableName);
    return table?.analytics?.freshness ?? DATA_FRESHNESS.NEAR_REALTIME;
  };

  /**
   * Get analytics stale time for a table.
   */
  getAnalyticsStaleTime = (tableName: string): number => {
    const table = this.tables.get(tableName);
    return table?.analytics?.staleTime ?? this.defaults.staleTime;
  };

  /**
   * Get all analytics-enabled tables.
   */
  getAnalyticsTables = (): ReadonlyArray<string> =>
    Array.from(this.tables.entries())
      .filter(([, config]) => config.analytics?.enabled)
      .map(([name]) => name);
}

// =============================================================================
// FACTORY
// =============================================================================

/**
 * Create a new TableRegistry instance.
 */
export const createTableRegistry = (
  tables: ReadonlyArray<UnifiedTableConfig> = [],
  defaults?: {
    staleTime?: number;
    gcTime?: number;
    conflictStrategy?: ConflictStrategy;
    debug?: boolean;
  },
): TableRegistry => new TableRegistry(tables, defaults);
