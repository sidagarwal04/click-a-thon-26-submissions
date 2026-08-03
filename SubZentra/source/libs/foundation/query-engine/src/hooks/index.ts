/**
 * Query Engine Hooks
 *
 * Two user-facing hooks for all data operations:
 * - useDLQueryEngine: Unified query hook (reads)
 * - useDLMutateQueryEngine: Unified mutation hook (writes)
 *
 * These hooks delegate ALL execution to Data Layer hooks:
 * - useDLAnalytics for DuckDB queries
 * - useDLGetList for transactional API queries
 * - useDLCreate, useDLUpdate, useDLDelete for mutations
 *
 * Query Engine handles routing, SQL compilation, and conversion only.
 *
 * @module hooks
 */

// =============================================================================
// MAIN HOOKS
// =============================================================================

export { useDLQueryEngine } from './use-dl-query-engine';

export { useDLMutateQueryEngine } from './use-dl-mutate-query-engine';

// =============================================================================
// TYPES
// =============================================================================

export {
  // Options
  type UseDLQueryEngineOptions,
  type UseDLMutateQueryEngineOptions,

  // Results (discriminated unions)
  type UseDLQueryEngineResult,
  type UseDLMutateQueryEngineResult,

  // Supporting types
  type DownloadProgress,
  type MutationOperation,
  type MutationResultOperation,
  type HookExecutionPath,
  type ExecutionPath,
  type HookDataSource,
  type DataSource,

  // Constants (const object patterns)
  EXECUTION_PATHS,
  DATA_SOURCES,
  MUTATION_OPERATIONS,
  MUTATION_RESULT_OPERATIONS,
  INITIAL_DOWNLOAD_STATE,

  // Type guards
  isAnalyticsResult,
  isTransactionalResult,
  isPendingResult,
  isMutationOperation,
} from './types';
