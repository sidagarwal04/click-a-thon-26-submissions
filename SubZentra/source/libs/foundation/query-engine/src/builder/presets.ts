/**
 * Query Presets for Foundation Query Engine
 *
 * Pre-configured query builders for common use cases.
 *
 * @module builder/presets
 */

import type { FilterExpression, FilterOperator, FilterPrimitive } from '../types/filter';
import { isFilterAndGroup, isFilterCondition, isFilterOrGroup } from '../types/filter';
import type { Query } from '../types/query';
import { FRESHNESS_REQUIREMENTS } from '../types/query';
import type { DateRangeSpec, TimeGranularity } from '../types/time';
import { PRESET_DATE_RANGES, TIME_GRANULARITIES } from '../types/time';
import { QueryBuilder } from './query-builder';

// =============================================================================
// PRESET TYPES
// =============================================================================

/**
 * Common preset options
 */
export interface PresetOptions {
  /** Limit results */
  readonly limit?: number;
  /** Timezone */
  readonly timezone?: string;
  /** Include total count */
  readonly withTotal?: boolean;
}

/**
 * Time series preset options
 */
export interface TimeSeriesPresetOptions extends PresetOptions {
  /** Date range */
  readonly dateRange?: DateRangeSpec;
  /** Time granularity */
  readonly granularity?: TimeGranularity;
}

const applyCommonOptions = (builder: QueryBuilder, options?: PresetOptions): void => {
  if (!options) {
    return;
  }

  if (options.limit !== undefined) {
    builder.limit(options.limit);
  }

  if (options.timezone !== undefined) {
    builder.timezone(options.timezone);
  }

  if (options.withTotal !== undefined) {
    builder.withTotal(options.withTotal);
  }
};

const addFilterExpression = (builder: QueryBuilder, expression: FilterExpression): void => {
  if (isFilterCondition(expression)) {
    const values = expression.values ?? [];
    builder.filter(expression.member, expression.operator, ...values);
    return;
  }

  if (isFilterAndGroup(expression)) {
    builder.and(...expression.and);
    return;
  }

  if (isFilterOrGroup(expression)) {
    builder.or(...expression.or);
  }
};

// =============================================================================
// AGGREGATE PRESETS
// =============================================================================

/**
 * Create a simple count query
 */
export const countQuery = (countAlias = 'total_count', options?: PresetOptions): Query => {
  const builder = new QueryBuilder().count(countAlias);
  applyCommonOptions(builder, options);
  return builder.build();
};

/**
 * Create a count by dimension query
 */
export const countByDimension = (
  dimension: string,
  countAlias = 'count',
  options?: PresetOptions,
): Query => {
  const builder = new QueryBuilder().count(countAlias).dimension(dimension).desc(countAlias);
  applyCommonOptions(builder, options);
  return builder.build();
};

/**
 * Create a sum by dimension query
 */
export const sumByDimension = (
  sumColumn: string,
  dimension: string,
  sumAlias = 'total',
  options?: PresetOptions,
): Query => {
  const builder = new QueryBuilder().sum(sumColumn, sumAlias).dimension(dimension).desc(sumAlias);
  applyCommonOptions(builder, options);
  return builder.build();
};

// =============================================================================
// TIME SERIES PRESETS
// =============================================================================

const createTimeSeriesBuilder = (
  timeDimension: string,
  options?: TimeSeriesPresetOptions,
): QueryBuilder =>
  new QueryBuilder()
    .timeDimension(
      timeDimension,
      options?.granularity ?? TIME_GRANULARITIES.DAY,
      options?.dateRange ?? PRESET_DATE_RANGES.LAST_30_DAYS,
    )
    .asc(timeDimension);

/**
 * Create a time series count query
 */
export const timeSeriesCount = (
  timeDimension: string,
  options?: TimeSeriesPresetOptions,
): Query => {
  const builder = createTimeSeriesBuilder(timeDimension, options).count('count');
  applyCommonOptions(builder, options);
  return builder.build();
};

/**
 * Create a time series sum query
 */
export const timeSeriesSum = (
  sumColumn: string,
  timeDimension: string,
  sumAlias = 'total',
  options?: TimeSeriesPresetOptions,
): Query => {
  const builder = createTimeSeriesBuilder(timeDimension, options).sum(sumColumn, sumAlias);
  applyCommonOptions(builder, options);
  return builder.build();
};

/**
 * Create a time series with multiple metrics
 */
export const timeSeriesMetrics = (
  measures: ReadonlyArray<string>,
  timeDimension: string,
  options?: TimeSeriesPresetOptions,
): Query => {
  const builder = new QueryBuilder()
    .timeDimension(
      timeDimension,
      options?.granularity ?? TIME_GRANULARITIES.DAY,
      options?.dateRange ?? PRESET_DATE_RANGES.LAST_30_DAYS,
    )
    .asc(timeDimension);

  for (const measure of measures) {
    builder.measure(measure);
  }

  applyCommonOptions(builder, options);
  return builder.build();
};

// =============================================================================
// DASHBOARD PRESETS
// =============================================================================

/**
 * Create a KPI query (single aggregated value)
 */
export const kpiQuery = (
  measure: string,
  dateRange?: DateRangeSpec,
  timeDimension?: string,
): Query => {
  const builder = new QueryBuilder().measure(measure);

  if (timeDimension && dateRange) {
    builder.timeDimension(timeDimension, undefined, dateRange);
  }

  return builder.build();
};

/**
 * Create a comparison KPI query (current vs previous period)
 */
export const comparisonKpiQuery = (
  measure: string,
  timeDimension: string,
  currentRange: DateRangeSpec,
  previousRange: DateRangeSpec,
): Query => {
  return new QueryBuilder()
    .measure(measure)
    .timeDimensionWithComparison(timeDimension, TIME_GRANULARITIES.DAY, currentRange, previousRange)
    .build();
};

/**
 * Create a top N query
 */
export const topNQuery = (
  measure: string,
  dimension: string,
  n: number,
  options?: PresetOptions,
): Query => {
  const builder = new QueryBuilder()
    .measure(measure)
    .dimension(dimension)
    .orderBy(measure, 'desc')
    .limit(n);

  applyCommonOptions(builder, options);
  return builder.build();
};

// =============================================================================
// FILTERED PRESETS
// =============================================================================

/**
 * Create a filtered count query
 */
export const filteredCount = (
  filterMember: string,
  filterOperator: FilterOperator,
  filterValues: ReadonlyArray<FilterPrimitive>,
  countAlias = 'filtered_count',
): Query => {
  return new QueryBuilder()
    .count(countAlias)
    .filter(filterMember, filterOperator, ...filterValues)
    .build();
};

/**
 * Create a filtered aggregation query
 */
export const filteredAggregation = (
  measure: string,
  filterMember: string,
  filterOperator: FilterOperator,
  filterValues: ReadonlyArray<FilterPrimitive>,
): Query => {
  return new QueryBuilder()
    .measure(measure)
    .filter(filterMember, filterOperator, ...filterValues)
    .build();
};

// =============================================================================
// REAL-TIME PRESETS
// =============================================================================

/**
 * Create a real-time subscription query
 */
export const realtimeQuery = (
  measures: ReadonlyArray<string>,
  dimensions?: ReadonlyArray<string>,
): Query => {
  const builder = new QueryBuilder().subscribe().freshness(FRESHNESS_REQUIREMENTS.REALTIME);

  for (const measure of measures) {
    builder.measure(measure);
  }

  if (dimensions) {
    builder.groupBy(...dimensions);
  }

  return builder.build();
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Extend a preset with additional configuration
 */
export const extendPreset = (preset: Query, configure: (builder: QueryBuilder) => void): Query => {
  const builder = new QueryBuilder();

  if (preset.queryId !== undefined) {
    builder.id(preset.queryId);
  }

  if (preset.measures) {
    for (const measure of preset.measures) {
      if (measure.member === '*') {
        builder.count(measure.alias);
      } else {
        builder.measure(measure.member, measure.aggregation, {
          alias: measure.alias,
          distinct: measure.distinct,
        });
      }
    }
  }

  if (preset.dimensions) {
    for (const dimension of preset.dimensions) {
      builder.dimension(dimension.member, {
        alias: dimension.alias,
        format: dimension.format,
      });
    }
  }

  if (preset.timeDimensions) {
    for (const timeDimension of preset.timeDimensions) {
      builder.timeDimensionWithComparison(
        timeDimension.dimension,
        timeDimension.granularity ?? TIME_GRANULARITIES.DAY,
        timeDimension.dateRange ?? PRESET_DATE_RANGES.TODAY,
        timeDimension.compareTo ?? PRESET_DATE_RANGES.TODAY,
      );
    }
  }

  if (preset.filters) {
    for (const filter of preset.filters) {
      addFilterExpression(builder, filter);
    }
  }

  if (preset.joins) {
    for (const join of preset.joins) {
      builder.addJoin(join);
    }
  }

  if (preset.orderBy) {
    for (const orderBy of preset.orderBy) {
      builder.orderBy(orderBy.member, orderBy.direction);
    }
  }

  if (preset.limit !== undefined) {
    builder.limit(preset.limit);
  }

  if (preset.offset !== undefined) {
    builder.offset(preset.offset);
  }

  if (preset.timezone !== undefined) {
    builder.timezone(preset.timezone);
  }

  if (preset.ungrouped !== undefined) {
    builder.ungrouped(preset.ungrouped);
  }

  if (preset.withTotal !== undefined) {
    builder.withTotal(preset.withTotal);
  }

  if (preset.subscription !== undefined) {
    builder.subscribe(preset.subscription);
  }

  if (preset.freshness !== undefined) {
    builder.freshness(preset.freshness);
  }

  if (preset.backendHint !== undefined) {
    builder.backendHint(preset.backendHint);
  }

  configure(builder);
  return builder.build();
};
