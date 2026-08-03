/**
 * Foundation Query Engine Types
 *
 * Exports all query-engine-owned type definitions.
 *
 * NOTE: Branded types (SqlTableName, MemberRef, QueryId, SqlIdentifier, ExecutionId)
 * are NOT re-exported here. Import them directly from:
 *   @open-zentra/foundation-data-model
 *
 * @module types
 */

// =============================================================================
// Filter Value (query-engine owned)
// =============================================================================

export type { FilterValue } from './filter';

// =============================================================================
// Dimension Types
// =============================================================================

export {
  DIMENSION_FORMAT_TYPES,
  type DimensionFormatType,
  type DimensionSpec,
  isDimensionSpec,
  extractTableFromDimension,
  extractColumnFromDimension,
  getDimensionAlias,
  createDimension,
} from './dimension';

// =============================================================================
// Aggregation Types
// =============================================================================

export {
  AGGREGATIONS,
  COUNT_AGGREGATIONS,
  NUMERIC_AGGREGATIONS,
  DISTINCT_AGGREGATIONS,
  type Aggregation,
  type CountAggregation,
  type NumericAggregation,
  type DistinctAggregation,
  isAggregation,
  isCountAggregation,
  isNumericAggregation,
  isDistinctAggregation,
  getAggregationSqlFunction,
} from './aggregation';

// =============================================================================
// Measure Types
// =============================================================================

export {
  MEASURE_FORMAT_TYPES,
  type MeasureFormatType,
  type MeasureSpec,
  isMeasureSpec,
  extractTableFromMeasure,
  extractColumnFromMeasure,
  getMeasureAlias,
  measureUsesDistinct,
  createMeasure,
  sumMeasure,
  countMeasure,
  countDistinctMeasure,
  avgMeasure,
  minMeasure,
  maxMeasure,
} from './measure';

// =============================================================================
// Filter Types
// =============================================================================

export {
  EQUALITY_OPERATORS,
  COMPARISON_OPERATORS,
  STRING_OPERATORS,
  SET_OPERATORS,
  NULL_OPERATORS,
  ARRAY_OPERATORS,
  FILTER_OPERATORS,
  VALUELESS_FILTER_OPERATORS,
  SINGLE_VALUE_FILTER_OPERATORS,
  MULTI_VALUE_FILTER_OPERATORS,
  type EqualityOperator,
  type ComparisonOperator,
  type StringOperator,
  type SetOperator,
  type NullOperator,
  type ArrayOperator,
  type FilterOperator,
  type FilterPrimitive,
  type FilterCondition,
  type FilterAndGroup,
  type FilterOrGroup,
  type FilterGroup,
  type FilterExpression,
  isFilterOperator,
  isFilterCondition,
  isFilterAndGroup,
  isFilterOrGroup,
  isFilterGroup,
  isFilterExpression,
  operatorRequiresValues,
  operatorAcceptsMultipleValues,
  extractTableFromFilter,
  extractColumnFromFilter,
  createFilterCondition,
  andFilter,
  orFilter,
  eq,
  neq,
  gt,
  gte,
  lt,
  lte,
  between,
  inList,
  notInList,
  contains,
  startsWith,
  endsWith,
  isNull,
  isNotNull,
} from './filter';

// =============================================================================
// Join Types
// =============================================================================

export {
  JOIN_TYPES,
  type JoinType,
  type JoinSpec,
  isJoinType,
  isJoinSpec,
  extractLeftTable,
  extractRightTable,
  extractLeftColumn,
  extractRightColumn,
  extractTablesFromJoin,
  getJoinSqlKeyword,
  createJoin,
  innerJoin,
  leftJoin,
  rightJoin,
  fullJoin,
} from './join';

// =============================================================================
// Order Types
// =============================================================================

export {
  ORDER_DIRECTIONS,
  NULLS_HANDLING,
  type OrderDirection,
  type NullsHandling,
  type OrderBySpec,
  isOrderDirection,
  isOrderBySpec,
  extractTableFromOrderBy,
  extractColumnFromOrderBy,
  createOrderBy,
  asc,
  desc,
} from './order';

// =============================================================================
// Query Types
// =============================================================================

export {
  QUERY_BACKENDS,
  QUERY_DATA_SOURCES,
  FRESHNESS_REQUIREMENTS,
  type QueryBackend,
  type DataSource,
  type FreshnessRequirement,
  type Query,
  type QueryValidationResult,
  type QueryValidationError,
  type QueryValidationWarning,
  isQuery,
  queryRequiresDuckDB,
  isMutationQuery,
  isReadQuery,
  isQueryBackend,
  isFreshnessRequirement,
  getQueryOperation,
  createListQuery,
  createGetQuery,
  createCountQuery,
} from './query';

// =============================================================================
// Table Types
// =============================================================================

// NOTE: For ConflictStrategy type, import directly from @open-zentra/foundation-data-model
export {
  TABLE_SOURCES,
  TABLE_LOAD_STATES,
  TABLE_FILE_TYPES,
  ANALYTICS_FRESHNESS_LEVELS,
  type TableSource,
  type TableLoadState,
  type TableFileType,
  type TableApiFunctions,
  type ParquetFileInfo,
  type TableConfig,
  type RegisterTableOptions,
  isTableSource,
  isTableLoadState,
  isConflictStrategy,
  isTableReady,
  tableNeedsLoading,
  isTableLoading,
  hasTableError,
  isTableStale,
  hasNewerServerData,
  tableHasListApi,
  tableHasMutationApi,
} from './table';

// =============================================================================
// Decision Types
// =============================================================================

export {
  DECISION_PATHS,
  DECISION_REASONS,
  type ExecutionPath,
  type DecisionReason,
  type DecisionResult,
  type DecisionFactors,
  type DecisionTableConfig,
  type DecisionContext,
  type DecisionOptions,
  type DecisionRule,
  isExecutionPath,
  isApiPath,
  isDuckDBPath,
} from './decision';

// =============================================================================
// Config Types
// =============================================================================

export {
  DEFAULT_STALE_TIME,
  DEFAULT_CONFIG,
  type QueryEngineConfig,
  type ResolvedQueryEngineConfig,
  resolveQueryEngineConfig,
} from './config';

// =============================================================================
// Time Types (Granularities, date ranges, time dimensions)
// =============================================================================

export {
  TIME_GRANULARITIES,
  TIME_UNITS,
  PRESET_DATE_RANGES,
  GRANULARITY_MS,
  GRANULARITY_ORDER,
  type TimeGranularity,
  type TimeUnit,
  type PresetDateRange,
  type DateRange,
  type RelativeDateRange,
  type DateRangeSpec,
  type TimeDimensionSpec,
  isPresetDateRange,
  isDateRange,
  isDateRangeTuple,
  isRelativeDateRange,
  isTimeGranularity,
  isTimeUnit,
  compareGranularities,
  isGranularityFiner,
  getDateTruncUnit,
  resolvePresetDateRange,
} from './time';

// =============================================================================
// Schema Types (Tables, measures, dimensions)
// =============================================================================

export {
  MEASURE_DATA_TYPES,
  DIMENSION_TYPES,
  MEMBER_VISIBILITY,
  RELATIONSHIP_CARDINALITIES,
  JOIN_RELATIONSHIP_CARDINALITIES,
  CARDINALITY_TO_JOIN_CARDINALITY,
  type MeasureDataType,
  type DimensionType,
  type MemberVisibility,
  type RelationshipCardinality,
  type JoinDefinitionType,
  type JoinRelationshipCardinality,
  type ColumnDefinition,
  type DimensionDefinition,
  type TimeDimensionDefinition,
  type MeasureDefinition,
  type RelationshipDefinition,
  type PreAggregationDefinition,
  type TableDefinition,
  type SchemaDefinition,
  isDimensionType,
  isTimeDimension,
  isMemberVisibility,
  getTableMeasures,
  getTableDimensions,
  getVisibleMembers,
  createMemberRef,
} from './schema-definition';

// =============================================================================
// Result Types (Query results, execution metadata)
// =============================================================================

export {
  EXECUTION_STATUS,
  type ExecutionStatus,
  type ResultRow,
  type ResultColumn,
  type QueryResult,
  type ExecutionTiming,
  type ExecutionMetadata,
  type ExecutionError,
  type ExecutionResult,
  type AggregationResult,
  isExecutionStatus,
  isSuccessfulExecution,
  isFailedExecution,
  createEmptyResult,
  createExecutionMetadata,
  completeExecution,
  transformResult,
  paginateResult,
} from './result';
