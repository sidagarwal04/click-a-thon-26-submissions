/**
 * Conflict resolver
 * @module conflicts/resolver
 */

import isEqual from 'react-fast-compare';

import {
  CONFLICT_STRATEGY,
  type ConflictContext,
  type ConflictResult,
  type ConflictStrategy,
  type MergeConfig,
} from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  createSingletonFactory,
  Disposable,
} from '@open-zentra/foundation-utils';

import type { IConflictResolver } from '../core/interfaces';
import { DEFAULT_MERGE_CONFIG, strategyResolvers } from './strategies';

/**
 * Conflict resolver configuration
 */
export interface ConflictResolverConfig {
  /** Default strategy to use */
  defaultStrategy: ConflictStrategy;
  /** Per-table strategy overrides */
  tableStrategies?: Record<string, ConflictStrategy>;
  /** Per-table merge configs */
  tableMergeConfigs?: Record<string, MergeConfig>;
  /** Global merge config */
  mergeConfig?: MergeConfig;
  /** Callback when conflict requires review */
  onConflictReview?: (context: ConflictContext<unknown>, result: ConflictResult<unknown>) => void;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Default conflict resolver configuration
 */
const DEFAULT_RESOLVER_CONFIG: Required<
  Omit<ConflictResolverConfig, 'onConflictReview' | 'tableStrategies' | 'tableMergeConfigs'>
> = {
  defaultStrategy: CONFLICT_STRATEGY.LAST_WRITE_WINS,
  mergeConfig: DEFAULT_MERGE_CONFIG,
  debug: false,
};

/**
 * Conflict resolver class with proper disposal
 */
export class ConflictResolver extends Disposable implements IConflictResolver {
  private config: ConflictResolverConfig;
  private logger;

  constructor(config: Partial<ConflictResolverConfig> = {}) {
    super();
    this.config = {
      ...DEFAULT_RESOLVER_CONFIG,
      ...config,
    };
    this.logger = createDebugLogger('ConflictResolver', this.config.debug ?? false);
  }

  /**
   * Get strategy for a table
   */
  getStrategy(tableName: string): ConflictStrategy {
    this.ensureNotDisposed();
    return this.config.tableStrategies?.[tableName] ?? this.config.defaultStrategy;
  }

  /**
   * Get merge config for a table
   */
  getMergeConfig(tableName: string): MergeConfig {
    return (
      this.config.tableMergeConfigs?.[tableName] ?? this.config.mergeConfig ?? DEFAULT_MERGE_CONFIG
    );
  }

  /**
   * Resolve a conflict
   */
  resolve<T>(context: ConflictContext<T>): ConflictResult<T> {
    this.ensureNotDisposed();

    const strategy = this.getStrategy(context.tableName);
    const resolver = strategyResolvers[strategy];
    const mergeConfig = this.getMergeConfig(context.tableName);

    this.logger.debug(
      `Resolving conflict for ${context.tableName}:${context.entityId} using ${strategy}`,
    );

    const result = resolver(context, mergeConfig);

    if (result.requiresReview && this.config.onConflictReview) {
      this.config.onConflictReview(context, result);
    }

    this.logger.debug('Resolution result:', {
      winner: result.winner,
      requiresReview: result.requiresReview,
      mergedFields: result.mergedFields,
      conflictedFields: result.conflictedFields,
    });

    return result;
  }

  /**
   * Check if there's a conflict between server and client data using deep equality
   */
  hasConflict<T>(
    serverData: T,
    clientData: T,
    serverTimestamp: number,
    clientTimestamp: number,
  ): boolean {
    this.ensureNotDisposed();

    // If timestamps are the same, assume no conflict
    if (serverTimestamp === clientTimestamp) {
      return false;
    }

    // If data is the same using deep equality, no conflict
    if (isEqual(serverData, clientData)) {
      return false;
    }

    // Server has been updated since client's last sync
    return serverTimestamp > clientTimestamp;
  }

  /**
   * Set strategy for a table
   */
  setTableStrategy(tableName: string, strategy: ConflictStrategy): void {
    this.ensureNotDisposed();

    if (!this.config.tableStrategies) {
      this.config.tableStrategies = {};
    }
    this.config.tableStrategies[tableName] = strategy;
  }

  /**
   * Set merge config for a table
   */
  setTableMergeConfig(tableName: string, config: MergeConfig): void {
    this.ensureNotDisposed();

    if (!this.config.tableMergeConfigs) {
      this.config.tableMergeConfigs = {};
    }
    this.config.tableMergeConfigs[tableName] = config;
  }

  /**
   * Dispose implementation
   */
  protected onDispose(): void {
    this.logger.debug('Disposed');
  }
}

/**
 * Singleton factory for conflict resolver
 */
const conflictResolverFactory = createSingletonFactory(
  (config: Partial<ConflictResolverConfig> | undefined) => new ConflictResolver(config),
  {
    name: 'ConflictResolver',
    onDispose: (instance) => {
      if (instance instanceof ConflictResolver) {
        instance.dispose();
      }
    },
  },
);

/**
 * Get or create conflict resolver singleton instance.
 */
export const getConflictResolver = (config?: Partial<ConflictResolverConfig>): ConflictResolver =>
  conflictResolverFactory.getInstance(config);

/**
 * Reset conflict resolver singleton (for testing).
 */
export const resetConflictResolver = (): void => {
  void conflictResolverFactory.reset();
};

/**
 * Create a new ConflictResolver instance (non-singleton).
 */
export const createConflictResolver = (
  config?: Partial<ConflictResolverConfig>,
): ConflictResolver => new ConflictResolver(config);
