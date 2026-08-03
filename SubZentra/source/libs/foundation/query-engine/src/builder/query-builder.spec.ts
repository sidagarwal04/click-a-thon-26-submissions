/**
 * Query Builder Tests
 *
 * @module builder/query-builder.spec
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { AGGREGATIONS } from '../types/aggregation';
import { FILTER_OPERATORS } from '../types/filter';
import { JOIN_TYPES } from '../types/join';
import { ORDER_DIRECTIONS } from '../types/order';
import { FRESHNESS_REQUIREMENTS, QUERY_BACKENDS } from '../types/query';
import { PRESET_DATE_RANGES, TIME_GRANULARITIES } from '../types/time';
import {
  comparisonKpiQuery,
  countByDimension,
  countQuery,
  extendPreset,
  filteredAggregation,
  filteredCount,
  kpiQuery,
  realtimeQuery,
  sumByDimension,
  timeSeriesCount,
  timeSeriesMetrics,
  timeSeriesSum,
  topNQuery,
} from './presets';
import { createQueryBuilder, filterCondition, QueryBuilder } from './query-builder';

describe('QueryBuilder', () => {
  let builder: QueryBuilder;

  beforeEach(() => {
    builder = createQueryBuilder();
  });

  describe('createQueryBuilder', () => {
    it('should create a new builder instance', () => {
      const builder = createQueryBuilder();
      expect(builder).toBeInstanceOf(QueryBuilder);
    });
  });

  describe('query identity', () => {
    it('should set query ID', () => {
      const query = builder.id('my-query-id').build();
      expect((query as any).queryId).toBe('my-query-id');
    });

    it('should generate unique query ID', () => {
      const query = builder.generateId('test').build();
      expect((query as any).queryId).toMatch(/^test_/);
    });
  });

  describe('measures', () => {
    it('should add measure with aggregation', () => {
      const query = builder.measure('orders.total', 'sum').build();
      expect(query.measures).toHaveLength(1);
      expect(query.measures![0].member).toBe('orders.total');
      expect(query.measures![0].aggregation).toBe('sum');
    });

    it('should add multiple measures', () => {
      const query = builder
        .measures(
          { member: 'orders.total', aggregation: 'sum' },
          { member: 'orders.count', aggregation: 'count' },
        )
        .build();
      expect(query.measures).toHaveLength(2);
    });

    it('should add count measure', () => {
      const query = builder.count('order_count').build();

      expect(query.measures).toHaveLength(1);
      expect(query.measures![0].aggregation).toBe(AGGREGATIONS.COUNT);
      expect(query.measures![0].alias).toBe('order_count');
    });

    it('should add count distinct measure', () => {
      const query = builder.countDistinct('orders.user_id', 'unique_users').build();

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.COUNT);
      expect(measure.distinct).toBe(true);
      expect(measure.alias).toBe('unique_users');
    });

    it('should add sum measure', () => {
      const query = builder.sum('orders.amount', 'total').build();

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.SUM);
    });

    it('should add avg measure', () => {
      const query = builder.avg('orders.amount', 'average').build();

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.AVG);
    });

    it('should add min measure', () => {
      const query = builder.min('orders.amount', 'minimum').build();

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.MIN);
    });

    it('should add max measure', () => {
      const query = builder.max('orders.amount', 'maximum').build();

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.MAX);
    });
  });

  describe('dimensions', () => {
    it('should add dimension as DimensionSpec', () => {
      const query = builder.dimension('orders.status').build();
      expect(query.dimensions).toHaveLength(1);
      expect(query.dimensions![0].member).toBe('orders.status');
    });

    it('should add dimension with options', () => {
      const query = builder
        // 'uppercase' is not one of DIMENSION_FORMAT_TYPES; the point of this
        // test is that options travel through, so it uses a real format.
        .dimension('orders.status', { alias: 'status', format: 'currency' })
        .build();
      expect(query.dimensions![0].alias).toBe('status');
      expect(query.dimensions![0].format).toBe('currency');
    });

    it('should add multiple dimensions via groupBy', () => {
      const query = builder.groupBy('orders.status', 'orders.region').build();

      expect(query.dimensions).toHaveLength(2);
      expect(query.dimensions![0].member).toBe('orders.status');
      expect(query.dimensions![1].member).toBe('orders.region');
    });
  });

  describe('time dimensions', () => {
    it('should add time dimension with granularity', () => {
      const query = builder.timeDimension('orders.created_at', TIME_GRANULARITIES.DAY).build();

      expect(query.timeDimensions).toHaveLength(1);
      expect(query.timeDimensions![0].granularity).toBe(TIME_GRANULARITIES.DAY);
    });

    it('should add time dimension with date range', () => {
      const query = builder
        .timeDimension(
          'orders.created_at',
          TIME_GRANULARITIES.MONTH,
          PRESET_DATE_RANGES.LAST_30_DAYS,
        )
        .build();

      expect(query.timeDimensions![0].dateRange).toBe(PRESET_DATE_RANGES.LAST_30_DAYS);
    });

    it('should add time dimension with comparison', () => {
      const query = builder
        .timeDimensionWithComparison(
          'orders.created_at',
          TIME_GRANULARITIES.DAY,
          PRESET_DATE_RANGES.LAST_7_DAYS,
          PRESET_DATE_RANGES.LAST_30_DAYS,
        )
        .build();

      expect(query.timeDimensions![0].compareTo).toBe(PRESET_DATE_RANGES.LAST_30_DAYS);
    });
  });

  describe('filters', () => {
    it('should add filter condition', () => {
      const query = builder.filter('orders.status', FILTER_OPERATORS.EQUALS, 'completed').build();

      expect(query.filters).toHaveLength(1);
      const filter = query.filters![0] as any;
      expect(filter.member).toBe('orders.status');
      expect(filter.operator).toBe(FILTER_OPERATORS.EQUALS);
      expect(filter.values).toContain('completed');
    });

    it('should add equals filter', () => {
      const query = builder.equals('orders.status', 'completed').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.EQUALS);
    });

    it('should add not equals filter', () => {
      const query = builder.notEquals('orders.status', 'cancelled').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.NOT_EQUALS);
    });

    it('should add gt filter', () => {
      const query = builder.gt('orders.amount', 100).build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.GT);
    });

    it('should add gte filter', () => {
      const query = builder.gte('orders.amount', 100).build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.GTE);
    });

    it('should add lt filter', () => {
      const query = builder.lt('orders.amount', 100).build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.LT);
    });

    it('should add lte filter', () => {
      const query = builder.lte('orders.amount', 100).build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.LTE);
    });

    it('should add IN filter', () => {
      const query = builder.in('orders.status', ['pending', 'processing']).build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.IN);
      expect(filter.values).toHaveLength(2);
    });

    it('should add NOT IN filter', () => {
      const query = builder.notIn('orders.status', ['cancelled']).build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.NOT_IN);
    });

    it('should add contains filter', () => {
      const query = builder.contains('users.email', '@example.com').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.CONTAINS);
    });

    it('should add startsWith filter', () => {
      const query = builder.startsWith('users.name', 'John').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.STARTS_WITH);
    });

    it('should add endsWith filter', () => {
      const query = builder.endsWith('users.email', '.com').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.ENDS_WITH);
    });

    it('should add isNull filter', () => {
      const query = builder.isNull('orders.cancelled_at').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.IS_NULL);
    });

    it('should add isNotNull filter', () => {
      const query = builder.isNotNull('orders.completed_at').build();
      const filter = query.filters![0] as any;
      expect(filter.operator).toBe(FILTER_OPERATORS.IS_NOT_NULL);
    });

    it('should add AND logical filter', () => {
      const query = builder
        .and(
          filterCondition('orders.status', FILTER_OPERATORS.EQUALS, 'completed'),
          filterCondition('orders.amount', FILTER_OPERATORS.GT, 100),
        )
        .build();

      const filter = query.filters![0] as any;
      expect(filter.and).toHaveLength(2);
    });

    it('should add OR logical filter', () => {
      const query = builder
        .or(
          filterCondition('orders.status', FILTER_OPERATORS.EQUALS, 'pending'),
          filterCondition('orders.status', FILTER_OPERATORS.EQUALS, 'processing'),
        )
        .build();

      const filter = query.filters![0] as any;
      expect(filter.or).toHaveLength(2);
    });
  });

  describe('joins', () => {
    it('should add inner join with JoinSpec format', () => {
      const query = builder.innerJoin('orders.user_id', 'users.id').build();

      expect(query.joins).toHaveLength(1);
      expect(query.joins![0].type).toBe(JOIN_TYPES.INNER);
      expect(query.joins![0].left).toBe('orders.user_id');
      expect(query.joins![0].right).toBe('users.id');
    });

    it('should add left join', () => {
      const query = builder.leftJoin('orders.user_id', 'users.id').build();

      expect(query.joins![0].type).toBe(JOIN_TYPES.LEFT);
    });

    it('should add join with alias', () => {
      const query = builder.innerJoin('orders.user_id', 'users.id', 'u').build();

      expect(query.joins![0].alias).toBe('u');
    });
  });

  describe('ordering', () => {
    it('should add order by ascending', () => {
      const query = builder.orderBy('orders.created_at', ORDER_DIRECTIONS.ASC).build();

      expect(query.orderBy).toHaveLength(1);
      expect(query.orderBy![0].direction).toBe(ORDER_DIRECTIONS.ASC);
    });

    it('should add order by descending', () => {
      const query = builder.orderBy('orders.amount', ORDER_DIRECTIONS.DESC).build();

      expect(query.orderBy![0].direction).toBe(ORDER_DIRECTIONS.DESC);
    });

    it('should add asc shorthand', () => {
      const query = builder.asc('orders.created_at').build();
      expect(query.orderBy![0].direction).toBe(ORDER_DIRECTIONS.ASC);
    });

    it('should add desc shorthand', () => {
      const query = builder.desc('orders.amount').build();
      expect(query.orderBy![0].direction).toBe(ORDER_DIRECTIONS.DESC);
    });
  });

  describe('pagination', () => {
    it('should set limit', () => {
      const query = builder.limit(100).build();
      expect(query.limit).toBe(100);
    });

    it('should set offset', () => {
      const query = builder.offset(50).build();
      expect(query.offset).toBe(50);
    });

    it('should set page', () => {
      const query = builder.page(3, 20).build();
      expect(query.limit).toBe(20);
      expect(query.offset).toBe(40); // (3-1) * 20
    });

    it('should set page 1 with offset 0', () => {
      const query = builder.page(1, 10).build();
      expect(query.limit).toBe(10);
      expect(query.offset).toBe(0);
    });

    it('should throw for page(0, 10)', () => {
      expect(() => builder.page(0, 10)).toThrow('pageNumber must be >= 1, got 0');
    });

    it('should throw for negative pageNumber', () => {
      expect(() => builder.page(-1, 10)).toThrow('pageNumber must be >= 1, got -1');
    });

    it('should throw for pageSize < 1', () => {
      expect(() => builder.page(1, 0)).toThrow('pageSize must be >= 1, got 0');
    });
  });

  describe('options', () => {
    it('should set timezone', () => {
      const query = builder.timezone('America/New_York').build();
      expect((query as any).timezone).toBe('America/New_York');
    });

    it('should set ungrouped', () => {
      const query = builder.ungrouped().build();
      expect((query as any).ungrouped).toBe(true);
    });

    it('should set withTotal', () => {
      const query = builder.withTotal().build();
      expect((query as any).withTotal).toBe(true);
    });

    it('should set subscription', () => {
      const query = builder.subscribe().build();
      expect((query as any).subscription).toBe(true);
    });

    it('should set freshness', () => {
      const query = builder.freshness(FRESHNESS_REQUIREMENTS.REALTIME).build();
      expect((query as any).freshness).toBe(FRESHNESS_REQUIREMENTS.REALTIME);
    });

    it('should set backend hint', () => {
      const query = builder.backendHint(QUERY_BACKENDS.ANALYTICAL).build();
      expect((query as any).backendHint).toBe(QUERY_BACKENDS.ANALYTICAL);
    });
  });

  describe('clone', () => {
    it('should create independent copy', () => {
      const original = builder.measure('orders.total', 'sum').dimension('orders.status').limit(100);

      const cloned = original.clone();
      cloned.measure('orders.count', 'count').limit(50);

      const originalQuery = original.build();
      const clonedQuery = cloned.build();

      expect(originalQuery.measures).toHaveLength(1);
      expect(clonedQuery.measures).toHaveLength(2);
      expect(originalQuery.limit).toBe(100);
      expect(clonedQuery.limit).toBe(50);
    });
  });

  describe('reset', () => {
    it('should clear all builder state', () => {
      const resetBuilder = builder
        .measure('orders.total', 'sum')
        .dimension('orders.status')
        .filter('orders.amount', FILTER_OPERATORS.GT, 100)
        .reset();

      expect(() => resetBuilder.build()).toThrow();
    });
  });

  describe('non-empty query validation', () => {
    it('should allow filter-only query', () => {
      const query = builder.filter('orders.status', FILTER_OPERATORS.EQUALS, 'completed').build();
      expect(query.filters).toHaveLength(1);
    });

    it('should allow join-only query', () => {
      const query = builder.leftJoin('orders.user_id', 'users.id').build();
      expect(query.joins).toHaveLength(1);
    });

    it('should allow pagination-only query', () => {
      const query = builder.limit(10).offset(20).build();
      expect(query.limit).toBe(10);
      expect(query.offset).toBe(20);
    });

    it('should allow options-only query', () => {
      const query = builder.timezone('UTC').withTotal(true).build();
      expect(query.timezone).toBe('UTC');
      expect(query.withTotal).toBe(true);
    });

    it('should reject empty query', () => {
      expect(() => createQueryBuilder().build()).toThrow();
    });
  });

  describe('complex query building', () => {
    it('should build a complete analytical query', () => {
      const query = builder
        .generateId('analytics')
        .sum('orders.total_amount', 'total_amount')
        .count('order_count')
        .dimension('orders.status')
        .groupBy('orders.region')
        .timeDimension(
          'orders.created_at',
          TIME_GRANULARITIES.MONTH,
          PRESET_DATE_RANGES.LAST_30_DAYS,
        )
        .filter('orders.status', FILTER_OPERATORS.NOT_EQUALS, 'cancelled')
        .gt('orders.amount', 0)
        .leftJoin('orders.user_id', 'users.id', 'u')
        .desc('total_amount')
        .limit(10)
        .offset(0)
        .timezone('UTC')
        .withTotal()
        .build();

      expect((query as any).queryId).toMatch(/^analytics_/);
      expect(query.measures).toHaveLength(2);
      expect(query.dimensions).toHaveLength(2);
      expect(query.timeDimensions).toHaveLength(1);
      expect(query.filters).toHaveLength(2);
      expect(query.joins).toHaveLength(1);
      expect(query.orderBy).toHaveLength(1);
      expect(query.limit).toBe(10);
      expect((query as any).timezone).toBe('UTC');
      expect((query as any).withTotal).toBe(true);
    });
  });
});

describe('filterCondition helper', () => {
  it('should create filter condition', () => {
    const condition = filterCondition('orders.status', FILTER_OPERATORS.EQUALS, 'completed');

    expect(condition.member).toBe('orders.status');
    expect(condition.operator).toBe(FILTER_OPERATORS.EQUALS);
    expect(condition.values).toContain('completed');
  });

  it('should create condition with multiple values', () => {
    const condition = filterCondition(
      'orders.status',
      FILTER_OPERATORS.IN,
      'pending',
      'processing',
    );

    expect(condition.values).toHaveLength(2);
  });

  it('should create condition without values', () => {
    const condition = filterCondition('orders.cancelled_at', FILTER_OPERATORS.IS_NULL);

    expect(condition.values).toBeUndefined();
  });
});

describe('Query Presets', () => {
  describe('countQuery', () => {
    it('should create count query', () => {
      const query = countQuery();
      expect(query.measures).toHaveLength(1);
    });

    it('should accept custom alias', () => {
      const query = countQuery('total_orders');
      const measure = query.measures![0] as any;
      expect(measure.alias).toBe('total_orders');
    });

    it('should accept options', () => {
      const query = countQuery('count', { limit: 10, withTotal: true });
      expect(query.limit).toBe(10);
      expect((query as any).withTotal).toBe(true);
    });
  });

  describe('countByDimension', () => {
    it('should create count by dimension query', () => {
      const query = countByDimension('orders.status');

      expect(query.measures).toHaveLength(1);
      expect(query.dimensions![0].member).toBe('orders.status');
      expect(query.orderBy).toBeDefined();
    });
  });

  describe('sumByDimension', () => {
    it('should create sum by dimension query', () => {
      const query = sumByDimension('orders.amount', 'orders.status', 'total');

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.SUM);
      expect(query.dimensions![0].member).toBe('orders.status');
    });
  });

  describe('timeSeriesCount', () => {
    it('should create time series count query', () => {
      const query = timeSeriesCount('orders.created_at');

      expect(query.measures).toHaveLength(1);
      expect(query.timeDimensions).toHaveLength(1);
      expect(query.timeDimensions![0].granularity).toBe(TIME_GRANULARITIES.DAY);
    });

    it('should accept custom options', () => {
      const query = timeSeriesCount('orders.created_at', {
        granularity: TIME_GRANULARITIES.MONTH,
        dateRange: PRESET_DATE_RANGES.LAST_YEAR,
      });

      expect(query.timeDimensions![0].granularity).toBe(TIME_GRANULARITIES.MONTH);
      expect(query.timeDimensions![0].dateRange).toBe(PRESET_DATE_RANGES.LAST_YEAR);
    });
  });

  describe('timeSeriesSum', () => {
    it('should create time series sum query', () => {
      const query = timeSeriesSum('orders.amount', 'orders.created_at');

      const measure = query.measures![0];
      expect(measure.aggregation).toBe(AGGREGATIONS.SUM);
      expect(query.timeDimensions).toHaveLength(1);
    });
  });

  describe('timeSeriesMetrics', () => {
    it('should create time series with multiple metrics', () => {
      const query = timeSeriesMetrics(['orders.total_amount', 'orders.count'], 'orders.created_at');

      expect(query.measures).toHaveLength(2);
      expect(query.timeDimensions).toHaveLength(1);
    });
  });

  describe('kpiQuery', () => {
    it('should create KPI query', () => {
      const query = kpiQuery('orders.total_amount');
      expect(query.measures![0].member).toBe('orders.total_amount');
    });

    it('should add date range with time dimension', () => {
      const query = kpiQuery(
        'orders.total_amount',
        PRESET_DATE_RANGES.LAST_30_DAYS,
        'orders.created_at',
      );

      expect(query.timeDimensions).toHaveLength(1);
    });
  });

  describe('comparisonKpiQuery', () => {
    it('should create comparison KPI query', () => {
      const query = comparisonKpiQuery(
        'orders.total_amount',
        'orders.created_at',
        PRESET_DATE_RANGES.LAST_7_DAYS,
        PRESET_DATE_RANGES.LAST_30_DAYS,
      );

      expect(query.measures![0].member).toBe('orders.total_amount');
      expect(query.timeDimensions![0].compareTo).toBe(PRESET_DATE_RANGES.LAST_30_DAYS);
    });
  });

  describe('topNQuery', () => {
    it('should create top N query', () => {
      const query = topNQuery('orders.total_amount', 'orders.user_id', 10);

      expect(query.measures![0].member).toBe('orders.total_amount');
      expect(query.dimensions![0].member).toBe('orders.user_id');
      expect(query.limit).toBe(10);
      expect(query.orderBy![0].direction).toBe('desc');
    });
  });

  describe('filteredCount', () => {
    it('should create filtered count query', () => {
      const query = filteredCount('orders.status', FILTER_OPERATORS.EQUALS, ['completed']);

      expect(query.measures).toHaveLength(1);
      expect(query.filters).toHaveLength(1);
    });
  });

  describe('filteredAggregation', () => {
    it('should create filtered aggregation query', () => {
      const query = filteredAggregation(
        'orders.total_amount',
        'orders.status',
        FILTER_OPERATORS.EQUALS,
        ['completed'],
      );

      expect(query.measures![0].member).toBe('orders.total_amount');
      expect(query.filters).toHaveLength(1);
    });
  });

  describe('realtimeQuery', () => {
    it('should create realtime query', () => {
      const query = realtimeQuery(['orders.count']);

      expect((query as any).subscription).toBe(true);
      expect((query as any).freshness).toBe(FRESHNESS_REQUIREMENTS.REALTIME);
    });

    it('should include dimensions', () => {
      const query = realtimeQuery(['orders.count'], ['orders.status']);

      expect(query.dimensions![0].member).toBe('orders.status');
    });
  });

  describe('extendPreset', () => {
    it('should extend preset with additional configuration', () => {
      const base = countQuery();
      const extended = extendPreset(base, (builder) => {
        builder.dimension('orders.status').limit(50);
      });

      expect(extended.measures).toHaveLength(1);
      expect(extended.dimensions![0].member).toBe('orders.status');
      expect(extended.limit).toBe(50);
    });

    it('should preserve original preset values', () => {
      const base = timeSeriesCount('orders.created_at', {
        granularity: TIME_GRANULARITIES.MONTH,
      });
      const extended = extendPreset(base, (builder) => {
        builder.filter('orders.status', FILTER_OPERATORS.EQUALS, 'completed');
      });

      expect(extended.timeDimensions![0].granularity).toBe(TIME_GRANULARITIES.MONTH);
      expect(extended.filters).toHaveLength(1);
    });
  });
});
