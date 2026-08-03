/**
 * Query Builder for Testing
 *
 * Provides a fluent API for building test Query objects.
 *
 * @module builders/query-builder
 */

import { QueryId, Timestamp } from '@open-zentra/foundation-data-model';

// =============================================================================
// Types
// =============================================================================

/**
 * Aggregation function types
 */
export type AggregationType = 'sum' | 'count' | 'avg' | 'min' | 'max' | 'countDistinct';

/**
 * Sort direction
 */
export type SortDirection = 'asc' | 'desc';

/**
 * Filter operator types
 */
export type FilterOperator =
  | 'equals'
  | 'notEquals'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'contains'
  | 'startsWith'
  | 'endsWith'
  | 'in'
  | 'notIn'
  | 'between';

/**
 * Time granularity for time dimensions
 */
export type TimeGranularity =
  | 'second'
  | 'minute'
  | 'hour'
  | 'day'
  | 'week'
  | 'month'
  | 'quarter'
  | 'year';

/**
 * Measure definition for test queries
 */
export interface TestMeasure {
  readonly member: string;
  readonly aggregation: AggregationType;
  readonly alias?: string;
}

/**
 * Dimension definition for test queries
 */
export interface TestDimension {
  readonly member: string;
  readonly alias?: string;
}

/**
 * Time dimension definition for test queries
 */
export interface TestTimeDimension {
  readonly member: string;
  readonly granularity: TimeGranularity;
  readonly alias?: string;
}

/**
 * Filter definition for test queries
 */
export interface TestFilter {
  readonly member: string;
  readonly operator: FilterOperator;
  readonly value: unknown;
}

/**
 * Sort definition for test queries
 */
export interface TestSort {
  readonly member: string;
  readonly direction: SortDirection;
}

/**
 * Complete test query object
 */
export interface TestQuery {
  readonly id: QueryId;
  readonly table: string;
  readonly measures: readonly TestMeasure[];
  readonly dimensions: readonly TestDimension[];
  readonly timeDimensions: readonly TestTimeDimension[];
  readonly filters: readonly TestFilter[];
  readonly order: readonly TestSort[];
  readonly limit?: number;
  readonly offset?: number;
  readonly createdAt: Timestamp;
}

// =============================================================================
// Query Builder
// =============================================================================

/**
 * Builder for creating test Query objects
 *
 * @example
 * ```typescript
 * const query = QueryBuilder.create()
 *   .withTable('events')
 *   .withMeasure('count', 'count')
 *   .withDimension('browser')
 *   .withFilter('country', 'equals', 'US')
 *   .withLimit(100)
 *   .build();
 * ```
 */
export class QueryBuilder {
  private _id: QueryId;
  private _table = 'test_table';
  private _measures: TestMeasure[] = [];
  private _dimensions: TestDimension[] = [];
  private _timeDimensions: TestTimeDimension[] = [];
  private _filters: TestFilter[] = [];
  private _order: TestSort[] = [];
  private _limit?: number;
  private _offset?: number;
  private _createdAt: Timestamp;

  private constructor() {
    this._id = QueryId.create();
    this._createdAt = Timestamp.now();
  }

  /**
   * Create a new QueryBuilder
   */
  static create(): QueryBuilder {
    return new QueryBuilder();
  }

  /**
   * Set the query ID
   */
  withId(id?: QueryId): this {
    this._id = id ?? QueryId.create();
    return this;
  }

  /**
   * Set the target table
   */
  withTable(table: string): this {
    this._table = table;
    return this;
  }

  /**
   * Add a measure
   */
  withMeasure(member: string, aggregation: AggregationType, alias?: string): this {
    this._measures.push({ member, aggregation, alias });
    return this;
  }

  /**
   * Add multiple measures
   */
  withMeasures(measures: TestMeasure[]): this {
    this._measures.push(...measures);
    return this;
  }

  /**
   * Add a dimension
   */
  withDimension(member: string, alias?: string): this {
    this._dimensions.push({ member, alias });
    return this;
  }

  /**
   * Add multiple dimensions
   */
  withDimensions(dimensions: TestDimension[]): this {
    this._dimensions.push(...dimensions);
    return this;
  }

  /**
   * Add a time dimension
   */
  withTimeDimension(member: string, granularity: TimeGranularity, alias?: string): this {
    this._timeDimensions.push({ member, granularity, alias });
    return this;
  }

  /**
   * Add a filter
   */
  withFilter(member: string, operator: FilterOperator, value: unknown): this {
    this._filters.push({ member, operator, value });
    return this;
  }

  /**
   * Add multiple filters
   */
  withFilters(filters: TestFilter[]): this {
    this._filters.push(...filters);
    return this;
  }

  /**
   * Add a sort order
   */
  withOrder(member: string, direction: SortDirection = 'asc'): this {
    this._order.push({ member, direction });
    return this;
  }

  /**
   * Set the limit
   */
  withLimit(limit: number): this {
    this._limit = limit;
    return this;
  }

  /**
   * Set the offset
   */
  withOffset(offset: number): this {
    this._offset = offset;
    return this;
  }

  /**
   * Set the creation timestamp
   */
  withCreatedAt(timestamp: Timestamp): this {
    this._createdAt = timestamp;
    return this;
  }

  /**
   * Build the test query
   */
  build(): TestQuery {
    return {
      id: this._id,
      table: this._table,
      measures: [...this._measures],
      dimensions: [...this._dimensions],
      timeDimensions: [...this._timeDimensions],
      filters: [...this._filters],
      order: [...this._order],
      limit: this._limit,
      offset: this._offset,
      createdAt: this._createdAt,
    };
  }
}

/**
 * Create a quick test query with minimal configuration
 *
 * @example
 * ```typescript
 * const query = quickQuery({ table: 'events', limit: 10 });
 * ```
 */
export function quickQuery(overrides: Partial<TestQuery> = {}): TestQuery {
  return {
    id: overrides.id ?? QueryId.create(),
    table: overrides.table ?? 'test_table',
    measures: overrides.measures ?? [],
    dimensions: overrides.dimensions ?? [],
    timeDimensions: overrides.timeDimensions ?? [],
    filters: overrides.filters ?? [],
    order: overrides.order ?? [],
    limit: overrides.limit,
    offset: overrides.offset,
    createdAt: overrides.createdAt ?? Timestamp.now(),
  };
}
