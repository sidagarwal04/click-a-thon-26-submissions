/**
 * Decision Types
 *
 * Types for the Decision Engine that routes queries to API or DuckDB.
 *
 * @module types/decision
 */

import type { DataFreshnessLevel, Operation } from '@open-zentra/foundation-data-model';

import { QUERY_ENGINE_PATHS } from '../internal/constants';
import type { Query } from './query';

/**
 * Canonical query-engine execution paths used by DecisionEngine.
 */
export const DECISION_PATHS = {
  API: QUERY_ENGINE_PATHS.API,
  DUCKDB: QUERY_ENGINE_PATHS.DUCKDB,
} as const;

/**
 * Execution path type used by DecisionEngine.
 */
export type ExecutionPath = (typeof DECISION_PATHS)[keyof typeof DECISION_PATHS];

// =============================================================================
// DECISION REASONS
// =============================================================================

/**
 * Reasons why a particular execution path was chosen.
 *
 * Every branch in DecisionEngine maps to one of these constants so that the
 * `reason` field on `DecisionResult` is fully typed.
 */
export const DECISION_REASONS = {
  // API Path reasons
  MUTATION_USES_API: 'Mutation operations always use HTTP API',
  SIMPLE_QUERY_WITH_API: 'Simple query on single table with list API available',

  // DuckDB Path reasons
  HAS_JOINS: 'Query has joins - requires DuckDB',
  HAS_MEASURES: 'Query has aggregations - requires DuckDB',
  MULTIPLE_TABLES: 'Query involves multiple tables - requires DuckDB',
  LOCAL_TABLE: 'Table is local-only - requires DuckDB',
  NO_LIST_API: 'No list API defined for table - requires DuckDB',
  ANALYTICS_PREFERRED: 'Analytics freshness allows DuckDB path',

  // Dynamic / edge-case reasons
  FORCED_PATH: 'Execution path forced by caller',
  NO_MUTATION_API: 'No mutation API defined for table',
  NO_API_AVAILABLE: 'No get or list API available for table',

  // Fallback reasons
  NO_DECISION: 'Unable to make routing decision',
} as const;

export type DecisionReason = (typeof DECISION_REASONS)[keyof typeof DECISION_REASONS];

// =============================================================================
// DECISION RESULT
// =============================================================================

/**
 * Result from the decision engine.
 *
 * Includes the chosen path, reason, and any warnings.
 */
export interface DecisionResult {
  /**
   * Chosen execution path: 'api' or 'duckdb'.
   */
  readonly path: ExecutionPath;

  /**
   * Reason for the decision, drawn from `DECISION_REASONS`.
   */
  readonly reason: DecisionReason;

  /**
   * Confidence score (0-100).
   * Higher = more certain about the decision.
   */
  readonly confidence: number;

  /**
   * For API path: which API function to use.
   */
  readonly apiFunction?: Operation;

  /**
   * For DuckDB path: tables that need to be loaded.
   */
  readonly tablesToLoad?: ReadonlyArray<string>;

  /**
   * Any warnings about the decision.
   */
  readonly warnings?: ReadonlyArray<string>;

  /**
   * Debug info about the decision factors.
   */
  readonly factors?: DecisionFactors;
}

/**
 * Factors considered in making the routing decision.
 */
export interface DecisionFactors {
  /** Is this a mutation operation? */
  readonly isMutation: boolean;
  /** Does query have joins? */
  readonly hasJoins: boolean;
  /** Does query have measures (aggregations)? */
  readonly hasMeasures: boolean;
  /** Number of tables involved */
  readonly tableCount: number;
  /** Are all tables API-backed? */
  readonly allTablesApi: boolean;
  /** Do all tables have list API? */
  readonly allTablesHaveApi: boolean;
  /** Is client currently online? */
  readonly isOnline: boolean;
  /** Are any tables local-only? */
  readonly hasLocalTables: boolean;
}

// =============================================================================
// DECISION CONTEXT
// =============================================================================

/**
 * Context passed to the decision engine.
 */
export interface DecisionContext {
  /**
   * Tables involved in the query (extracted from members).
   */
  readonly tables: ReadonlyArray<string>;

  /**
   * Operation being performed.
   */
  readonly operation: Operation;

  /**
   * Table configurations (from registry).
   */
  readonly tableConfigs: ReadonlyMap<string, DecisionTableConfig>;

  /**
   * Whether client is currently online.
   */
  readonly isOnline: boolean;

  /**
   * Whether DuckDB is available/initialized.
   */
  readonly isDuckDBAvailable?: boolean;
}

/**
 * Subset of table configuration needed by DecisionEngine.
 *
 * Compatible with query-engine and data-layer table registries.
 */
export interface DecisionTableConfig {
  readonly source?: string;
  readonly api?: {
    readonly list?: unknown;
    readonly get?: unknown;
    readonly create?: unknown;
    readonly update?: unknown;
    readonly delete?: unknown;
  };
  readonly analytics?: {
    readonly freshness?: DataFreshnessLevel;
  };
}

// =============================================================================
// DECISION OPTIONS
// =============================================================================

/**
 * Options for the decision engine.
 */
export interface DecisionOptions {
  /**
   * Force a specific execution path (bypasses decision logic).
   * Use for testing or explicit user preference.
   */
  readonly forcePath?: ExecutionPath;

  /**
   * Prefer DuckDB even for simple queries (analytics freshness).
   * Useful when eventual consistency is acceptable.
   */
  readonly preferAnalytics?: boolean;

  /**
   * Include detailed factors in result (for debugging).
   */
  readonly includeFactors?: boolean;
}

// =============================================================================
// DECISION RULE (data-driven engine)
// =============================================================================

/**
 * A single routing rule evaluated by the DecisionEngine.
 *
 * Rules are evaluated in priority order. The first rule whose `match()`
 * returns `true` wins, and its `decide()` provides the result. Consumers
 * may register custom rules to extend or override the built-in set.
 */
export interface DecisionRule {
  /** Human-readable rule name (for logging / diagnostics) */
  readonly name: string;

  /** Return `true` when this rule applies to the given query + context. */
  match(
    query: Query,
    context: DecisionContext,
    factors: DecisionFactors,
    options?: DecisionOptions,
  ): boolean;

  /** Produce the routing result. Only called when `match()` returned `true`. */
  decide(
    query: Query,
    context: DecisionContext,
    factors: DecisionFactors,
    options?: DecisionOptions,
  ): DecisionResult;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid execution path.
 */
export const isExecutionPath = (value: unknown): value is ExecutionPath => {
  return (
    typeof value === 'string' && Object.values(DECISION_PATHS).includes(value as ExecutionPath)
  );
};

/**
 * Check if decision result indicates API path.
 */
export const isApiPath = (result: DecisionResult): boolean => {
  return result.path === DECISION_PATHS.API;
};

/**
 * Check if decision result indicates DuckDB path.
 */
export const isDuckDBPath = (result: DecisionResult): boolean => {
  return result.path === DECISION_PATHS.DUCKDB;
};
