/**
 * Foundation Query Engine
 *
 * Curated root API for common usage patterns.
 * Prefer explicit module subpaths for advanced/internal usage:
 * - `@open-zentra/foundation-query-engine/builder`
 * - `@open-zentra/foundation-query-engine/compiler`
 * - `@open-zentra/foundation-query-engine/engine`
 * - `@open-zentra/foundation-query-engine/hooks`
 * - `@open-zentra/foundation-query-engine/schema`
 * - `@open-zentra/foundation-query-engine/types`
 *
 * @packageDocumentation
 */

// =============================================================================
// Builder API
// =============================================================================

export {
  QueryBuilder,
  createQueryBuilder,
  filterCondition,
  countQuery,
  countByDimension,
  sumByDimension,
  timeSeriesCount,
  timeSeriesSum,
  timeSeriesMetrics,
  kpiQuery,
  comparisonKpiQuery,
  topNQuery,
  filteredCount,
  filteredAggregation,
  realtimeQuery,
  extendPreset,
} from './builder';

// =============================================================================
// Hook API (execution integration)
// =============================================================================

export {
  useDLQueryEngine,
  useDLMutateQueryEngine,
  type UseDLQueryEngineOptions,
  type UseDLMutateQueryEngineOptions,
  type UseDLQueryEngineResult,
  type UseDLMutateQueryEngineResult,
  type DownloadProgress,
  type HookExecutionPath,
  type HookDataSource,
  type MutationOperation,
  type MutationResultOperation,
  EXECUTION_PATHS,
  DATA_SOURCES,
  MUTATION_OPERATIONS,
  MUTATION_RESULT_OPERATIONS,
  INITIAL_DOWNLOAD_STATE,
  isAnalyticsResult,
  isTransactionalResult,
  isPendingResult,
  isMutationOperation,
} from './hooks';

// =============================================================================
// Engine + Compiler API
// =============================================================================

export {
  DecisionEngine,
  createDecisionEngine,
  getDecisionEngine,
  resetDecisionEngine,
  hasDecisionEngineInstance,
  TableExtractor,
  createTableExtractor,
  getTableExtractor,
  resetTableExtractor,
  convertFiltersToArgs,
} from './engine';

export {
  SqlCompiler,
  QueryCompilationError,
  createSqlCompiler,
  getSqlCompiler,
  resetSqlCompiler,
  hasSqlCompilerInstance,
} from './compiler';

// =============================================================================
// Schema API
// =============================================================================

export {
  SchemaRegistry,
  createSchemaRegistry,
  validateSchema,
  validateQuery,
  schema,
  table,
  measure,
  dimension,
  timeDimension,
} from './schema';

// =============================================================================
// Core Types + Constants
// =============================================================================

export {
  QUERY_BACKENDS,
  QUERY_DATA_SOURCES,
  FRESHNESS_REQUIREMENTS,
  DECISION_PATHS,
  DECISION_REASONS,
  type Query,
  type QueryBackend,
  type DataSource,
  type FreshnessRequirement,
  type ExecutionPath,
  type DecisionReason,
  type DecisionResult,
} from './types';

// =============================================================================
// Member Reference Utilities
// =============================================================================

export {
  parseMemberRef,
  extractTableName,
  extractColumnName,
  type ParsedMemberRef,
} from './utils/member-ref';
