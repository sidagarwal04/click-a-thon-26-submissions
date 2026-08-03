/**
 * Query Builder for Foundation Query Engine
 *
 * Provides a fluent API for constructing Query objects.
 *
 * @module builder/query-builder
 */

import type { QueryId } from '@open-zentra/foundation-data-model';
import {
  MemberRef as MemberRefUtil,
  QueryId as QueryIdUtil,
} from '@open-zentra/foundation-data-model';

import type { Aggregation } from '../types/aggregation';
import { AGGREGATIONS } from '../types/aggregation';
import type { DimensionFormatType, DimensionSpec } from '../types/dimension';
import type {
  FilterAndGroup,
  FilterCondition,
  FilterExpression,
  FilterOperator,
  FilterOrGroup,
  FilterPrimitive,
} from '../types/filter';
import { FILTER_OPERATORS } from '../types/filter';
import type { JoinSpec, JoinType } from '../types/join';
import { JOIN_TYPES } from '../types/join';
import type { MeasureSpec } from '../types/measure';
import type { OrderBySpec, OrderDirection } from '../types/order';
import { ORDER_DIRECTIONS } from '../types/order';
import type { FreshnessRequirement, Query, QueryBackend } from '../types/query';
import type { DateRangeSpec, TimeDimensionSpec, TimeGranularity } from '../types/time';

type BuildQuery = {
  -readonly [K in keyof Query]?: Query[K];
};

// =============================================================================
// QUERY BUILDER CLASS
// =============================================================================

/**
 * Query Builder
 *
 * Fluent API for building Query objects.
 *
 * @example
 * ```ts
 * const query = new QueryBuilder()
 *   .measure('orders.total_amount', 'sum')
 *   .dimension('orders.status')
 *   .timeDimension('orders.created_at', 'month', 'last_30_days')
 *   .filter('orders.status', 'equals', 'completed')
 *   .orderBy('orders.total_amount', 'desc')
 *   .limit(100)
 *   .build();
 * ```
 */
export class QueryBuilder {
  private _queryId?: QueryId;
  private _measures: MeasureSpec[] = [];
  private _dimensions: DimensionSpec[] = [];
  private _timeDimensions: TimeDimensionSpec[] = [];
  private _filters: FilterExpression[] = [];
  private _joins: JoinSpec[] = [];
  private _orderSpecs: OrderBySpec[] = [];
  private _limitValue?: number;
  private _offsetValue?: number;
  private _timezoneValue?: string;
  private _ungroupedValue?: boolean;
  private _withTotalValue?: boolean;
  private _subscriptionValue?: boolean;
  private _freshnessValue?: FreshnessRequirement;
  private _backendHintValue?: QueryBackend;

  // ---------------------------------------------------------------------------
  // Query Identity
  // ---------------------------------------------------------------------------

  /**
   * Set a specific query ID
   */
  id = (queryId: QueryId | string): QueryBuilder => {
    this._queryId = typeof queryId === 'string' ? QueryIdUtil.from(queryId) : queryId;
    return this;
  };

  /**
   * Generate a new query ID
   */
  generateId = (prefix = 'qb'): QueryBuilder => {
    this._queryId = QueryIdUtil.create(prefix);
    return this;
  };

  // ---------------------------------------------------------------------------
  // Measures
  // ---------------------------------------------------------------------------

  /**
   * Add a measure with aggregation
   */
  measure = (
    member: string,
    aggregation: Aggregation = 'count',
    options?: { alias?: string; distinct?: boolean },
  ): QueryBuilder => {
    const measureSpec: MeasureSpec = {
      member,
      aggregation,
      alias: options?.alias,
      distinct: options?.distinct,
    };
    this._measures.push(measureSpec);
    return this;
  };

  /**
   * Add multiple measures
   */
  measures = (
    ...specs: Array<{ member: string; aggregation: Aggregation; alias?: string }>
  ): QueryBuilder => {
    for (const spec of specs) {
      this.measure(spec.member, spec.aggregation, { alias: spec.alias });
    }
    return this;
  };

  /**
   * Add a COUNT(*) measure
   */
  count = (alias = 'count'): QueryBuilder => this.measure('*', AGGREGATIONS.COUNT, { alias });

  /**
   * Add a COUNT(DISTINCT column) measure
   */
  countDistinct = (member: string, alias?: string): QueryBuilder =>
    this.measure(member, AGGREGATIONS.COUNT, {
      alias: alias ?? `${member.replace('.', '_')}_distinct`,
      distinct: true,
    });

  /**
   * Add a SUM(column) measure
   */
  sum = (member: string, alias?: string): QueryBuilder =>
    this.measure(member, AGGREGATIONS.SUM, {
      alias: alias ?? `${member.replace('.', '_')}_sum`,
    });

  /**
   * Add an AVG(column) measure
   */
  avg = (member: string, alias?: string): QueryBuilder =>
    this.measure(member, AGGREGATIONS.AVG, {
      alias: alias ?? `${member.replace('.', '_')}_avg`,
    });

  /**
   * Add a MIN(column) measure
   */
  min = (member: string, alias?: string): QueryBuilder =>
    this.measure(member, AGGREGATIONS.MIN, {
      alias: alias ?? `${member.replace('.', '_')}_min`,
    });

  /**
   * Add a MAX(column) measure
   */
  max = (member: string, alias?: string): QueryBuilder =>
    this.measure(member, AGGREGATIONS.MAX, {
      alias: alias ?? `${member.replace('.', '_')}_max`,
    });

  // ---------------------------------------------------------------------------
  // Dimensions
  // ---------------------------------------------------------------------------

  /**
   * Add a dimension
   */
  dimension = (
    member: string,
    options?: { alias?: string; format?: DimensionFormatType },
  ): QueryBuilder => {
    const dimensionSpec: DimensionSpec = {
      member,
      alias: options?.alias,
      format: options?.format,
    };
    this._dimensions.push(dimensionSpec);
    return this;
  };

  /**
   * Add multiple dimensions
   */
  groupBy = (...members: string[]): QueryBuilder => {
    for (const member of members) {
      this.dimension(member);
    }
    return this;
  };

  /**
   * Add dimensions with specs
   */
  dimensionSpecs = (...specs: DimensionSpec[]): QueryBuilder => {
    this._dimensions.push(...specs);
    return this;
  };

  // ---------------------------------------------------------------------------
  // Time Dimensions
  // ---------------------------------------------------------------------------

  /**
   * Add a time dimension with granularity and date range
   */
  timeDimension = (
    member: string,
    granularity?: TimeGranularity,
    dateRange?: DateRangeSpec,
  ): QueryBuilder => {
    this._timeDimensions.push({
      dimension: MemberRefUtil.from(member),
      granularity,
      dateRange,
    });
    return this;
  };

  /**
   * Add a time dimension with comparison
   */
  timeDimensionWithComparison = (
    member: string,
    granularity: TimeGranularity,
    dateRange: DateRangeSpec,
    compareTo: DateRangeSpec,
  ): QueryBuilder => {
    this._timeDimensions.push({
      dimension: MemberRefUtil.from(member),
      granularity,
      dateRange,
      compareTo,
    });
    return this;
  };

  // ---------------------------------------------------------------------------
  // Filters
  // ---------------------------------------------------------------------------

  /**
   * Add a filter condition
   */
  filter = (
    member: string,
    operator: FilterOperator,
    ...values: FilterPrimitive[]
  ): QueryBuilder => {
    const condition: FilterCondition = {
      member,
      operator,
      values: values.length > 0 ? values : undefined,
    };
    this._filters.push(condition);
    return this;
  };

  /**
   * Add an equals filter
   */
  equals = (member: string, value: FilterPrimitive): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.EQUALS, value);

  /**
   * Add a not equals filter
   */
  notEquals = (member: string, value: FilterPrimitive): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.NOT_EQUALS, value);

  /**
   * Add a greater than filter
   */
  gt = (member: string, value: number): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.GT, value);

  /**
   * Add a greater than or equal filter
   */
  gte = (member: string, value: number): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.GTE, value);

  /**
   * Add a less than filter
   */
  lt = (member: string, value: number): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.LT, value);

  /**
   * Add a less than or equal filter
   */
  lte = (member: string, value: number): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.LTE, value);

  /**
   * Add an IN filter
   */
  in = (member: string, values: FilterPrimitive[]): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.IN, ...values);

  /**
   * Add a NOT IN filter
   */
  notIn = (member: string, values: FilterPrimitive[]): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.NOT_IN, ...values);

  /**
   * Add a contains filter
   */
  contains = (member: string, value: string): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.CONTAINS, value);

  /**
   * Add a starts with filter
   */
  startsWith = (member: string, value: string): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.STARTS_WITH, value);

  /**
   * Add an ends with filter
   */
  endsWith = (member: string, value: string): QueryBuilder =>
    this.filter(member, FILTER_OPERATORS.ENDS_WITH, value);

  /**
   * Add a null check filter
   */
  isNull = (member: string): QueryBuilder => this.filter(member, FILTER_OPERATORS.IS_NULL);

  /**
   * Add a not null check filter
   */
  isNotNull = (member: string): QueryBuilder => this.filter(member, FILTER_OPERATORS.IS_NOT_NULL);

  /**
   * Add an AND logical filter
   */
  and = (...filters: FilterExpression[]): QueryBuilder => {
    const logicalFilter: FilterAndGroup = { and: filters };
    this._filters.push(logicalFilter);
    return this;
  };

  /**
   * Add an OR logical filter
   */
  or = (...filters: FilterExpression[]): QueryBuilder => {
    const logicalFilter: FilterOrGroup = { or: filters };
    this._filters.push(logicalFilter);
    return this;
  };

  // ---------------------------------------------------------------------------
  // Joins
  // ---------------------------------------------------------------------------

  /**
   * Add a join using object-based JoinSpec
   */
  join = (
    left: string,
    right: string,
    type: JoinType = JOIN_TYPES.INNER,
    alias?: string,
  ): QueryBuilder => {
    this._joins.push({
      left,
      right,
      type,
      alias,
    });
    return this;
  };

  /**
   * Add an inner join
   */
  innerJoin = (left: string, right: string, alias?: string): QueryBuilder =>
    this.join(left, right, JOIN_TYPES.INNER, alias);

  /**
   * Add a left join
   */
  leftJoin = (left: string, right: string, alias?: string): QueryBuilder =>
    this.join(left, right, JOIN_TYPES.LEFT, alias);

  /**
   * Add a full join specification
   */
  addJoin = (joinSpec: JoinSpec): QueryBuilder => {
    this._joins.push(joinSpec);
    return this;
  };

  // ---------------------------------------------------------------------------
  // Ordering
  // ---------------------------------------------------------------------------

  /**
   * Add an order by clause
   */
  orderBy = (member: string, direction: OrderDirection = ORDER_DIRECTIONS.ASC): QueryBuilder => {
    this._orderSpecs.push({
      member,
      direction,
    });
    return this;
  };

  /**
   * Add ascending order
   */
  asc = (member: string): QueryBuilder => this.orderBy(member, ORDER_DIRECTIONS.ASC);

  /**
   * Add descending order
   */
  desc = (member: string): QueryBuilder => this.orderBy(member, ORDER_DIRECTIONS.DESC);

  // ---------------------------------------------------------------------------
  // Pagination
  // ---------------------------------------------------------------------------

  /**
   * Set result limit
   */
  limit = (count: number): QueryBuilder => {
    this._limitValue = count;
    return this;
  };

  /**
   * Set result offset
   */
  offset = (count: number): QueryBuilder => {
    this._offsetValue = count;
    return this;
  };

  /**
   * Set page (convenience for limit/offset)
   *
   * @param pageNumber - 1-based page number (must be >= 1)
   * @param pageSize - Number of items per page (must be >= 1)
   */
  page = (pageNumber: number, pageSize: number): QueryBuilder => {
    if (pageNumber < 1) throw new Error(`pageNumber must be >= 1, got ${pageNumber}`);
    if (pageSize < 1) throw new Error(`pageSize must be >= 1, got ${pageSize}`);
    this._limitValue = pageSize;
    this._offsetValue = (pageNumber - 1) * pageSize;
    return this;
  };

  // ---------------------------------------------------------------------------
  // Options
  // ---------------------------------------------------------------------------

  /**
   * Set timezone
   */
  timezone = (tz: string): QueryBuilder => {
    this._timezoneValue = tz;
    return this;
  };

  /**
   * Set ungrouped flag
   */
  ungrouped = (value = true): QueryBuilder => {
    this._ungroupedValue = value;
    return this;
  };

  /**
   * Request total count
   */
  withTotal = (value = true): QueryBuilder => {
    this._withTotalValue = value;
    return this;
  };

  /**
   * Enable subscription
   */
  subscribe = (value = true): QueryBuilder => {
    this._subscriptionValue = value;
    return this;
  };

  /**
   * Set freshness requirement
   */
  freshness = (requirement: FreshnessRequirement): QueryBuilder => {
    this._freshnessValue = requirement;
    return this;
  };

  /**
   * Set backend hint
   */
  backendHint = (backend: QueryBackend): QueryBuilder => {
    this._backendHintValue = backend;
    return this;
  };

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  /**
   * Validate the builder state.
   *
   * QueryBuilder allows any non-empty query shape:
   * filters-only, joins-only, pagination-only, options-only, etc.
   * The only invalid state is a truly empty query.
   *
   * @returns Array of validation error messages (empty if valid)
   */
  validate = (): string[] => {
    const errors: string[] = [];

    const hasAnyContent =
      this._queryId !== undefined ||
      this._measures.length > 0 ||
      this._dimensions.length > 0 ||
      this._timeDimensions.length > 0 ||
      this._filters.length > 0 ||
      this._joins.length > 0 ||
      this._orderSpecs.length > 0 ||
      this._limitValue !== undefined ||
      this._offsetValue !== undefined ||
      this._timezoneValue !== undefined ||
      this._ungroupedValue !== undefined ||
      this._withTotalValue !== undefined ||
      this._subscriptionValue !== undefined ||
      this._freshnessValue !== undefined ||
      this._backendHintValue !== undefined;

    if (!hasAnyContent) {
      errors.push('Query must contain at least one clause or option');
    }

    return errors;
  };

  /**
   * Build the Query
   *
   * Uses a mutable construction type and returns a readonly Query.
   *
   * @throws Error if the query is empty
   */
  build = (): Query => {
    const validationErrors = this.validate();
    if (validationErrors.length > 0) {
      throw new Error(`Invalid query: ${validationErrors.join('; ')}`);
    }

    const query: BuildQuery = {};

    // Only include non-empty arrays and defined values
    if (this._queryId) {
      query.queryId = this._queryId;
    }

    if (this._measures.length > 0) {
      query.measures = [...this._measures];
    }

    if (this._dimensions.length > 0) {
      query.dimensions = [...this._dimensions];
    }

    if (this._timeDimensions.length > 0) {
      query.timeDimensions = [...this._timeDimensions];
    }

    if (this._filters.length > 0) {
      query.filters = [...this._filters];
    }

    if (this._joins.length > 0) {
      query.joins = [...this._joins];
    }

    if (this._orderSpecs.length > 0) {
      query.orderBy = [...this._orderSpecs];
    }

    if (this._limitValue !== undefined) {
      query.limit = this._limitValue;
    }

    if (this._offsetValue !== undefined) {
      query.offset = this._offsetValue;
    }

    if (this._timezoneValue) {
      query.timezone = this._timezoneValue;
    }

    if (this._ungroupedValue !== undefined) {
      query.ungrouped = this._ungroupedValue;
    }

    if (this._withTotalValue !== undefined) {
      query.withTotal = this._withTotalValue;
    }

    if (this._subscriptionValue !== undefined) {
      query.subscription = this._subscriptionValue;
    }

    if (this._freshnessValue) {
      query.freshness = this._freshnessValue;
    }

    if (this._backendHintValue) {
      query.backendHint = this._backendHintValue;
    }

    return query;
  };

  /**
   * Clone the builder
   */
  clone = (): QueryBuilder => {
    const cloned = new QueryBuilder();
    cloned._queryId = this._queryId;
    cloned._measures = [...this._measures];
    cloned._dimensions = [...this._dimensions];
    cloned._timeDimensions = [...this._timeDimensions];
    cloned._filters = [...this._filters];
    cloned._joins = [...this._joins];
    cloned._orderSpecs = [...this._orderSpecs];
    cloned._limitValue = this._limitValue;
    cloned._offsetValue = this._offsetValue;
    cloned._timezoneValue = this._timezoneValue;
    cloned._ungroupedValue = this._ungroupedValue;
    cloned._withTotalValue = this._withTotalValue;
    cloned._subscriptionValue = this._subscriptionValue;
    cloned._freshnessValue = this._freshnessValue;
    cloned._backendHintValue = this._backendHintValue;
    return cloned;
  };

  /**
   * Reset the builder
   */
  reset = (): QueryBuilder => {
    this._queryId = undefined;
    this._measures = [];
    this._dimensions = [];
    this._timeDimensions = [];
    this._filters = [];
    this._joins = [];
    this._orderSpecs = [];
    this._limitValue = undefined;
    this._offsetValue = undefined;
    this._timezoneValue = undefined;
    this._ungroupedValue = undefined;
    this._withTotalValue = undefined;
    this._subscriptionValue = undefined;
    this._freshnessValue = undefined;
    this._backendHintValue = undefined;
    return this;
  };
}

// =============================================================================
// FACTORY FUNCTION
// =============================================================================

/**
 * Create a new QueryBuilder instance
 */
export const createQueryBuilder = (): QueryBuilder => new QueryBuilder();

/**
 * Create a filter condition (for use with logical filters)
 */
export const filterCondition = (
  member: string,
  operator: FilterOperator,
  ...values: FilterPrimitive[]
): FilterCondition => ({
  member,
  operator,
  values: values.length > 0 ? values : undefined,
});
