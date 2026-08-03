/**
 * Decision Engine
 *
 * Intelligent routing engine that decides whether a query should be executed
 * via HTTP API (transactional) or DuckDB (analytics).
 *
 * Decision Rules (in priority order):
 * 1. Mutations → API (create/update/delete always via HTTP)
 * 2. Has joins → DuckDB (SQL required for joins)
 * 3. Has measures/aggregations → DuckDB (SQL required for aggregations)
 * 4. Multiple tables → DuckDB (implies joins needed)
 * 5. Local-only table → DuckDB (no API available)
 * 6. No list API defined → DuckDB (use Parquet files)
 * 7. Otherwise → API (simple query, real-time data)
 *
 * @module engine/decision-engine
 */

import {
  DATA_FRESHNESS,
  isMutationOperation,
  OPERATIONS,
  WRITE_OPERATIONS,
} from '@open-zentra/foundation-data-model';
import {
  createSingletonFactory,
  DisposedError,
  type IDisposable,
} from '@open-zentra/foundation-utils';

import type {
  DecisionContext,
  DecisionFactors,
  DecisionOptions,
  DecisionResult,
  DecisionRule,
} from '../types/decision';
import { DECISION_PATHS, DECISION_REASONS } from '../types/decision';
import type { Query } from '../types/query';
import { TableExtractor } from './table-extractor';

// =============================================================================
// DECISION ENGINE
// =============================================================================

/**
 * DecisionEngine - routes queries to API or DuckDB.
 *
 * Prefers API for simple queries (real-time via WebSocket).
 * Uses DuckDB only when necessary (joins, aggregations, no API).
 * Implements IDisposable for proper resource cleanup.
 *
 * @example
 * const engine = new DecisionEngine();
 *
 * const decision = engine.decide(query, {
 *   tables: ['users'],
 *   operation: 'list',
 *   tableConfigs: configsMap,
 *   isOnline: true,
 * });
 *
 * if (decision.path === 'api') {
 *   // Execute via HTTP API
 * } else {
 *   // Execute via DuckDB
 * }
 *
 * // Cleanup when done
 * engine.dispose();
 */
export class DecisionEngine implements IDisposable {
  private readonly tableExtractor: TableExtractor;
  private readonly rules: DecisionRule[];
  private _isDisposed = false;

  constructor(tableExtractor?: TableExtractor, customRules?: DecisionRule[]) {
    this.tableExtractor = tableExtractor ?? new TableExtractor();
    this.rules = customRules ?? [...DEFAULT_DECISION_RULES];
  }

  /**
   * Check if the engine is disposed.
   */
  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Dispose of resources.
   */
  dispose(): void {
    if (this._isDisposed) return;
    this._isDisposed = true;
  }

  /**
   * Ensure the engine is not disposed before use.
   */
  private ensureNotDisposed(): void {
    if (this._isDisposed) {
      throw new DisposedError('DecisionEngine');
    }
  }

  /**
   * Get the current ordered list of rules (for diagnostics / testing).
   */
  getRules = (): readonly DecisionRule[] => [...this.rules];

  /**
   * Add a custom rule at the given index (0-based). Rules at lower
   * indices are evaluated first and take precedence.
   */
  addRule = (rule: DecisionRule, index?: number): void => {
    if (index !== undefined && index >= 0 && index <= this.rules.length) {
      this.rules.splice(index, 0, rule);
    } else {
      // Append before the default fallback (last rule)
      this.rules.splice(this.rules.length - 1, 0, rule);
    }
  };

  /**
   * Remove a rule by name. Returns `true` if found and removed.
   */
  removeRule = (name: string): boolean => {
    const idx = this.rules.findIndex((r) => r.name === name);
    if (idx === -1) return false;
    this.rules.splice(idx, 1);
    return true;
  };

  /**
   * Make a routing decision for a query.
   *
   * @param query - The query
   * @param context - Decision context with tables, operation, and config
   * @param options - Optional decision options
   * @returns Decision result with path, reason, and confidence
   */
  decide = (query: Query, context: DecisionContext, options?: DecisionOptions): DecisionResult => {
    this.ensureNotDisposed();

    // Allow forced path for testing/override
    if (options?.forcePath) {
      return {
        path: options.forcePath,
        reason: DECISION_REASONS.FORCED_PATH,
        confidence: 100,
        factors: options.includeFactors ? this.computeFactors(query, context) : undefined,
      };
    }

    // Compute decision factors once
    const factors = this.computeFactors(query, context);

    // Evaluate rules in priority order — first match wins
    for (const rule of this.rules) {
      if (rule.match(query, context, factors, options)) {
        const result = rule.decide(query, context, factors, options);

        // Optionally strip factors from the result if not requested
        if (!options?.includeFactors && result.factors) {
          return {
            path: result.path,
            reason: result.reason,
            confidence: result.confidence,
            apiFunction: result.apiFunction,
            tablesToLoad: result.tablesToLoad,
            warnings: result.warnings,
          };
        }
        return result;
      }
    }

    // Unreachable with default rules (last rule is always-match fallback)
    return {
      path: DECISION_PATHS.API,
      reason: DECISION_REASONS.NO_DECISION,
      confidence: 0,
      factors: options?.includeFactors ? factors : undefined,
    };
  };

  /**
   * Compute decision factors from query and context.
   */
  computeFactors = (query: Query, context: DecisionContext): DecisionFactors => {
    const { tables, operation, tableConfigs, isOnline } = context;

    const isMutation = isMutationOperation(operation);
    const hasJoins = (query.joins?.length ?? 0) > 0;
    const hasMeasures = (query.measures?.length ?? 0) > 0;

    let allTablesApi = true;
    let allTablesHaveApi = true;
    let hasLocalTables = false;

    for (const tableName of tables) {
      const config = tableConfigs.get(tableName);
      if (!config) {
        allTablesApi = false;
        allTablesHaveApi = false;
        continue;
      }

      if (config.source === 'local') {
        hasLocalTables = true;
        allTablesApi = false;
      }

      if (!config.api?.list && !config.api?.get) {
        allTablesHaveApi = false;
      }
    }

    return {
      isMutation,
      hasJoins,
      hasMeasures,
      tableCount: tables.length,
      allTablesApi,
      allTablesHaveApi,
      isOnline,
      hasLocalTables,
    };
  };

  /**
   * Check if a query can use the API path (without full decision).
   */
  canUseApi = (query: Query, context: DecisionContext): boolean => {
    if ((query.joins?.length ?? 0) > 0) return false;
    if ((query.measures?.length ?? 0) > 0) return false;
    if (context.tables.length > 1) return false;

    const primaryTable = context.tables[0];
    const config = context.tableConfigs.get(primaryTable);

    if (!config) return false;
    if (config.source === 'local') return false;
    if (!config.api?.list && !config.api?.get) return false;

    return true;
  };

  /**
   * Check if a query requires DuckDB (without full decision).
   */
  requiresDuckDB = (query: Query): boolean => {
    if ((query.joins?.length ?? 0) > 0) return true;
    if ((query.measures?.length ?? 0) > 0) return true;
    const tables = this.tableExtractor.extract(query);
    if (tables.length > 1) return true;
    return false;
  };
}

// =============================================================================
// BUILT-IN DECISION RULES
// =============================================================================

/**
 * Rule 1: Mutations → API
 */
const mutationRule: DecisionRule = {
  name: 'mutation',
  match: (_query, _context, factors) => factors.isMutation,
  decide: (_query, context, factors) => {
    const { tables, operation, tableConfigs } = context;
    const primaryTable = tables[0];
    const config = tableConfigs.get(primaryTable);
    const mutationRef = (() => {
      switch (operation) {
        case WRITE_OPERATIONS.CREATE:
          return config?.api?.create;
        case WRITE_OPERATIONS.UPDATE:
          return config?.api?.update;
        case WRITE_OPERATIONS.DELETE:
          return config?.api?.delete;
        default:
          return undefined;
      }
    })();

    if (!mutationRef) {
      return {
        path: DECISION_PATHS.API,
        reason: DECISION_REASONS.NO_MUTATION_API,
        confidence: 0,
        warnings: [`Cannot perform '${operation}' - no API defined`],
        factors,
      };
    }

    return {
      path: DECISION_PATHS.API,
      reason: DECISION_REASONS.MUTATION_USES_API,
      confidence: 100,
      apiFunction: operation,
      factors,
    };
  },
};

/**
 * Rule 2: Has joins → DuckDB
 */
const joinsRule: DecisionRule = {
  name: 'has-joins',
  match: (_query, _context, factors) => factors.hasJoins,
  decide: (_query, context, factors) => ({
    path: DECISION_PATHS.DUCKDB,
    reason: DECISION_REASONS.HAS_JOINS,
    confidence: 100,
    tablesToLoad: [...context.tables],
    factors,
  }),
};

/**
 * Rule 3: Has measures → DuckDB
 */
const measuresRule: DecisionRule = {
  name: 'has-measures',
  match: (_query, _context, factors) => factors.hasMeasures,
  decide: (_query, context, factors) => ({
    path: DECISION_PATHS.DUCKDB,
    reason: DECISION_REASONS.HAS_MEASURES,
    confidence: 100,
    tablesToLoad: [...context.tables],
    factors,
  }),
};

/**
 * Rule 4: Multiple tables → DuckDB
 */
const multipleTablesRule: DecisionRule = {
  name: 'multiple-tables',
  match: (_query, _context, factors) => factors.tableCount > 1,
  decide: (_query, context, factors) => ({
    path: DECISION_PATHS.DUCKDB,
    reason: DECISION_REASONS.MULTIPLE_TABLES,
    confidence: 100,
    tablesToLoad: [...context.tables],
    factors,
  }),
};

/**
 * Rule 5: Local-only table → DuckDB
 */
const localTableRule: DecisionRule = {
  name: 'local-table',
  match: (_query, context, factors) => {
    if (factors.hasLocalTables) return true;
    const config = context.tableConfigs.get(context.tables[0]);
    return config?.source === 'local';
  },
  decide: (_query, _context, factors) => ({
    path: DECISION_PATHS.DUCKDB,
    reason: DECISION_REASONS.LOCAL_TABLE,
    confidence: 100,
    tablesToLoad: [],
    factors,
  }),
};

/**
 * Rule 6: No API available → DuckDB
 */
const noApiRule: DecisionRule = {
  name: 'no-api',
  match: (query, context) => {
    const primaryTable = context.tables[0];
    const config = context.tableConfigs.get(primaryTable);
    const wantsGet = !!query.entityId || context.operation === OPERATIONS.GET;
    const hasListApi = !!config?.api?.list;
    const hasGetApi = !!config?.api?.get;

    if (!wantsGet && !hasListApi) return true;
    if (wantsGet && !hasGetApi && !hasListApi) return true;
    return false;
  },
  decide: (query, context, factors) => {
    const primaryTable = context.tables[0];
    const wantsGet = !!query.entityId || context.operation === OPERATIONS.GET;

    return {
      path: DECISION_PATHS.DUCKDB,
      reason: wantsGet ? DECISION_REASONS.NO_API_AVAILABLE : DECISION_REASONS.NO_LIST_API,
      confidence: 100,
      tablesToLoad: [primaryTable],
      factors,
    };
  },
};

/**
 * Rule 7: Analytics preferred → DuckDB
 */
const analyticsPreferredRule: DecisionRule = {
  name: 'analytics-preferred',
  match: (_query, context, _factors, options) => {
    if (!options?.preferAnalytics) return false;
    const config = context.tableConfigs.get(context.tables[0]);
    const freshness = config?.analytics?.freshness as string | undefined;
    return freshness === DATA_FRESHNESS.EVENTUAL || freshness === 'eventual';
  },
  decide: (_query, context, factors) => ({
    path: DECISION_PATHS.DUCKDB,
    reason: DECISION_REASONS.ANALYTICS_PREFERRED,
    confidence: 80,
    tablesToLoad: [context.tables[0]],
    factors,
  }),
};

/**
 * Default fallback: Simple query → API
 *
 * Always matches — must be last in the rules list.
 */
const defaultApiRule: DecisionRule = {
  name: 'default-api',
  match: () => true,
  decide: (query, context, factors) => {
    const wantsGet = !!query.entityId || context.operation === OPERATIONS.GET;
    return {
      path: DECISION_PATHS.API,
      reason: DECISION_REASONS.SIMPLE_QUERY_WITH_API,
      confidence: 100,
      apiFunction: wantsGet ? OPERATIONS.GET : OPERATIONS.LIST,
      factors,
    };
  },
};

/**
 * Built-in decision rules evaluated in priority order.
 * Exported so consumers can inspect or fork the defaults.
 */
export const DEFAULT_DECISION_RULES: readonly DecisionRule[] = [
  mutationRule,
  joinsRule,
  measuresRule,
  multipleTablesRule,
  localTableRule,
  noApiRule,
  analyticsPreferredRule,
  defaultApiRule,
];

// =============================================================================
// FACTORY
// =============================================================================

/**
 * Create a new DecisionEngine instance.
 */
export const createDecisionEngine = (
  tableExtractor?: TableExtractor,
  customRules?: DecisionRule[],
): DecisionEngine => {
  return new DecisionEngine(tableExtractor, customRules);
};

// =============================================================================
// SINGLETON FACTORY
// =============================================================================

/**
 * Configuration for DecisionEngine singleton.
 */
export interface DecisionEngineConfig {
  readonly tableExtractor?: TableExtractor;
  readonly customRules?: DecisionRule[];
}

/**
 * Singleton factory for DecisionEngine.
 *
 * Use this when you need a shared DecisionEngine instance across the application.
 * The instance will be created once and reused for all subsequent calls.
 *
 * @example
 * ```typescript
 * // Get the singleton instance
 * const engine = getDecisionEngine();
 *
 * // Make decisions
 * const decision = engine.decide(query, context);
 *
 * // Reset for testing
 * await resetDecisionEngine();
 * ```
 */
const decisionEngineFactory = createSingletonFactory<DecisionEngine, DecisionEngineConfig>(
  (config) =>
    new DecisionEngine(
      config?.tableExtractor,
      config?.customRules ? [...config.customRules] : undefined,
    ),
  {
    name: 'DecisionEngine',
    warnOnConfigOverride: true,
    onDispose: (instance) => {
      if (instance instanceof DecisionEngine) {
        instance.dispose();
      }
    },
    defaultConfig: {},
  },
);

/**
 * Get the singleton DecisionEngine instance.
 */
export const getDecisionEngine = (config?: DecisionEngineConfig): DecisionEngine => {
  return decisionEngineFactory.getInstance(config);
};

/**
 * Reset the singleton DecisionEngine instance (for testing).
 */
export const resetDecisionEngine = async (): Promise<void> => {
  await decisionEngineFactory.reset();
};

/**
 * Check if a DecisionEngine singleton instance exists.
 */
export const hasDecisionEngineInstance = (): boolean => {
  return decisionEngineFactory.hasInstance();
};
