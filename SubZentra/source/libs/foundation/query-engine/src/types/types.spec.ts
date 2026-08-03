/**
 * Type Guards Tests
 *
 * @module types/types.spec
 */

import { describe, expect, it } from 'vitest';

import {
  isOperation,
  isReadOperation,
  isWriteOperation,
  MemberRef,
  OPERATIONS,
  QueryId,
  SqlTableName as TableName,
} from '@open-zentra/foundation-data-model';

import { AGGREGATIONS, isAggregation } from './aggregation';
import { DECISION_PATHS, isExecutionPath } from './decision';
import { extractTableFromDimension, isDimensionSpec } from './dimension';
import type { DimensionSpec } from './dimension';
import {
  FILTER_OPERATORS,
  isFilterAndGroup,
  isFilterCondition,
  isFilterExpression,
  isFilterOrGroup,
  operatorAcceptsMultipleValues,
  operatorRequiresValues,
} from './filter';
import { isJoinSpec, isJoinType, JOIN_TYPES } from './join';
import { isMeasureSpec } from './measure';
import { isMutationQuery, isQueryBackend, isReadQuery, QUERY_BACKENDS } from './query';
import {
  isDateRange,
  isDateRangeTuple,
  isPresetDateRange,
  isTimeGranularity,
  PRESET_DATE_RANGES,
  resolvePresetDateRange,
  TIME_GRANULARITIES,
} from './time';

describe('Common Types', () => {
  describe('TableName', () => {
    it('should create a TableName from string', () => {
      const tableName = TableName.from('users');
      expect(tableName).toBe('users');
    });

    it('should validate table names', () => {
      // Using .is() to check if a value is a valid TableName
      expect(TableName.is('users')).toBe(true);
      expect(TableName.is('user_orders')).toBe(true);
      expect(TableName.is('_private')).toBe(true);
      // Invalid names - numbers and hyphens not allowed in SQL identifiers
      expect(TableName.is('123invalid')).toBe(false);
      expect(TableName.is('user-orders')).toBe(false);
    });
  });

  describe('MemberRef', () => {
    it('should create a MemberRef from table and member', () => {
      const ref = MemberRef.from('orders.total');
      expect(ref).toBe('orders.total');
    });

    it('should parse a MemberRef', () => {
      const ref = MemberRef.from('orders.total');
      const parsed = MemberRef.parse(ref);
      expect(parsed.table).toBe('orders');
      expect(parsed.member).toBe('total');
    });

    it('should validate MemberRef format', () => {
      expect(MemberRef.is('orders.total')).toBe(true);
      expect(MemberRef.is('orders.')).toBe(false);
      expect(MemberRef.is('.total')).toBe(false);
      expect(MemberRef.is('orders')).toBe(false);
    });
  });

  describe('QueryId', () => {
    it('should create unique QueryIds', () => {
      const id1 = QueryId.create();
      const id2 = QueryId.create();
      expect(id1).not.toBe(id2);
      // QueryId returns a branded string
      expect(typeof id1).toBe('string');
      expect(id1.length).toBeGreaterThan(0);
    });

    it('should create QueryId with custom prefix', () => {
      const id = QueryId.create('custom');
      expect(id.startsWith('custom_')).toBe(true);
    });
  });
});

describe('Operation Type Guards', () => {
  describe('isOperation', () => {
    it('should return true for valid operations', () => {
      expect(isOperation(OPERATIONS.GET)).toBe(true);
      expect(isOperation(OPERATIONS.LIST)).toBe(true);
      expect(isOperation(OPERATIONS.CREATE)).toBe(true);
      expect(isOperation(OPERATIONS.UPDATE)).toBe(true);
      expect(isOperation(OPERATIONS.DELETE)).toBe(true);
      expect(isOperation('get')).toBe(true);
    });

    it('should return false for invalid operations', () => {
      expect(isOperation('invalid')).toBe(false);
      expect(isOperation('aggregate')).toBe(false);
      expect(isOperation(null)).toBe(false);
      expect(isOperation(123)).toBe(false);
    });
  });

  describe('isReadOperation', () => {
    it('should return true for read operations', () => {
      expect(isReadOperation(OPERATIONS.GET)).toBe(true);
      expect(isReadOperation(OPERATIONS.LIST)).toBe(true);
    });

    it('should return false for write operations', () => {
      expect(isReadOperation(OPERATIONS.CREATE)).toBe(false);
      expect(isReadOperation(OPERATIONS.UPDATE)).toBe(false);
      expect(isReadOperation(OPERATIONS.DELETE)).toBe(false);
    });
  });

  describe('isWriteOperation', () => {
    it('should return true for write operations', () => {
      expect(isWriteOperation(OPERATIONS.CREATE)).toBe(true);
      expect(isWriteOperation(OPERATIONS.UPDATE)).toBe(true);
      expect(isWriteOperation(OPERATIONS.DELETE)).toBe(true);
    });

    it('should return false for read operations', () => {
      expect(isWriteOperation(OPERATIONS.GET)).toBe(false);
      expect(isWriteOperation(OPERATIONS.LIST)).toBe(false);
    });
  });
});

describe('Query Type Guards', () => {
  describe('isQueryBackend', () => {
    it('should return true for valid backends', () => {
      expect(isQueryBackend(QUERY_BACKENDS.ANALYTICAL)).toBe(true);
      expect(isQueryBackend(QUERY_BACKENDS.TRANSACTIONAL)).toBe(true);
      expect(isQueryBackend('analytical')).toBe(true);
    });

    it('should return false for invalid backends', () => {
      expect(isQueryBackend('invalid')).toBe(false);
      expect(isQueryBackend(null)).toBe(false);
    });
  });

  describe('isMutationQuery', () => {
    it('should return true for queries with write operations', () => {
      expect(isMutationQuery({ operation: 'create' })).toBe(true);
      expect(isMutationQuery({ operation: 'update' })).toBe(true);
      expect(isMutationQuery({ operation: 'delete' })).toBe(true);
    });

    it('should return false for queries with read operations', () => {
      expect(isMutationQuery({ operation: 'get' })).toBe(false);
      expect(isMutationQuery({ operation: 'list' })).toBe(false);
      expect(isMutationQuery({})).toBe(false);
    });
  });

  describe('isReadQuery', () => {
    it('should return true for queries with read operations', () => {
      expect(isReadQuery({ operation: 'get' })).toBe(true);
      expect(isReadQuery({ operation: 'list' })).toBe(true);
      expect(isReadQuery({})).toBe(true); // default is read
    });

    it('should return false for queries with write operations', () => {
      expect(isReadQuery({ operation: 'create' })).toBe(false);
      expect(isReadQuery({ operation: 'update' })).toBe(false);
    });
  });

  describe('isExecutionPath', () => {
    it('should return true for valid decision paths', () => {
      expect(isExecutionPath(DECISION_PATHS.API)).toBe(true);
      expect(isExecutionPath(DECISION_PATHS.DUCKDB)).toBe(true);
    });

    it('should return false for invalid values', () => {
      expect(isExecutionPath('analytics')).toBe(false);
      expect(isExecutionPath(null)).toBe(false);
    });
  });
});

describe('Dimension Type Guards', () => {
  describe('isDimensionSpec', () => {
    it('should return true for valid DimensionSpec objects', () => {
      expect(isDimensionSpec({ member: 'orders.status' })).toBe(true);
      expect(isDimensionSpec({ member: 'orders.status', alias: 'status' })).toBe(true);
    });

    it('should return false for non-DimensionSpec values', () => {
      expect(isDimensionSpec('orders.status')).toBe(false);
      expect(isDimensionSpec(null)).toBe(false);
      expect(isDimensionSpec({})).toBe(false);
    });
  });

  describe('extractTableFromDimension', () => {
    it('should extract table name from DimensionSpec', () => {
      expect(extractTableFromDimension({ member: 'orders.status' })).toBe('orders');
    });

    it('should return the member itself if no table prefix', () => {
      // When there's no dot, it returns the entire member as the first split element
      expect(extractTableFromDimension({ member: 'status' } as DimensionSpec)).toBe('status');
    });
  });
});

describe('Filter Type Guards', () => {
  describe('isFilterCondition', () => {
    it('should return true for filter conditions', () => {
      const condition = {
        member: 'orders.status',
        operator: FILTER_OPERATORS.EQUALS,
        values: ['completed'],
      };
      expect(isFilterCondition(condition)).toBe(true);
    });

    it('should return false for logical filters', () => {
      const logical = { and: [] };
      expect(isFilterCondition(logical)).toBe(false);
    });
  });

  describe('isFilterAndGroup', () => {
    it('should return true for AND filters', () => {
      expect(isFilterAndGroup({ and: [] })).toBe(true);
    });

    it('should return false for other types', () => {
      expect(isFilterAndGroup({ or: [] })).toBe(false);
      expect(isFilterAndGroup({ member: 'a', operator: 'equals' })).toBe(false);
    });
  });

  describe('isFilterOrGroup', () => {
    it('should return true for OR filters', () => {
      expect(isFilterOrGroup({ or: [] })).toBe(true);
    });

    it('should return false for other types', () => {
      expect(isFilterOrGroup({ and: [] })).toBe(false);
    });
  });

  describe('isFilterExpression', () => {
    it('should return true for conditions and groups', () => {
      expect(isFilterExpression({ member: 'a', operator: 'equals' })).toBe(true);
      expect(isFilterExpression({ and: [] })).toBe(true);
      expect(isFilterExpression({ or: [] })).toBe(true);
    });
  });

  describe('operatorRequiresValues', () => {
    it('should return false for valueless operators', () => {
      expect(operatorRequiresValues(FILTER_OPERATORS.IS_NULL)).toBe(false);
      expect(operatorRequiresValues(FILTER_OPERATORS.IS_NOT_NULL)).toBe(false);
    });

    it('should return true for operators that require values', () => {
      expect(operatorRequiresValues(FILTER_OPERATORS.EQUALS)).toBe(true);
      expect(operatorRequiresValues(FILTER_OPERATORS.IN)).toBe(true);
      expect(operatorRequiresValues(FILTER_OPERATORS.CONTAINS)).toBe(true);
    });
  });

  describe('operatorAcceptsMultipleValues', () => {
    it('should return true for multi-value operators', () => {
      expect(operatorAcceptsMultipleValues(FILTER_OPERATORS.IN)).toBe(true);
      expect(operatorAcceptsMultipleValues(FILTER_OPERATORS.NOT_IN)).toBe(true);
    });

    it('should return false for single-value operators', () => {
      expect(operatorAcceptsMultipleValues(FILTER_OPERATORS.EQUALS)).toBe(false);
      expect(operatorAcceptsMultipleValues(FILTER_OPERATORS.CONTAINS)).toBe(false);
    });
  });
});

describe('Measure Type Guards', () => {
  describe('isMeasureSpec', () => {
    it('should return true for valid MeasureSpec objects', () => {
      const spec = {
        member: 'orders.amount',
        aggregation: AGGREGATIONS.SUM,
        alias: 'total',
      };
      expect(isMeasureSpec(spec)).toBe(true);
    });

    it('should return false for invalid values', () => {
      expect(isMeasureSpec('orders.total')).toBe(false);
      expect(isMeasureSpec({ member: 'a' })).toBe(false); // missing aggregation
    });
  });

  describe('isAggregation', () => {
    it('should return true for valid aggregations', () => {
      expect(isAggregation(AGGREGATIONS.COUNT)).toBe(true);
      expect(isAggregation(AGGREGATIONS.SUM)).toBe(true);
      expect(isAggregation('sum')).toBe(true);
    });

    it('should return false for invalid aggregations', () => {
      expect(isAggregation('invalid')).toBe(false);
    });
  });
});

describe('Time Type Guards', () => {
  describe('isPresetDateRange', () => {
    it('should return true for preset ranges', () => {
      expect(isPresetDateRange(PRESET_DATE_RANGES.TODAY)).toBe(true);
      expect(isPresetDateRange(PRESET_DATE_RANGES.LAST_30_DAYS)).toBe(true);
      expect(isPresetDateRange('last_7_days')).toBe(true);
    });

    it('should return false for other date range types', () => {
      expect(isPresetDateRange({ from: '2024-01-01', to: '2024-01-31' })).toBe(false);
      expect(isPresetDateRange(['2024-01-01', '2024-01-31'])).toBe(false);
    });
  });

  describe('isDateRange', () => {
    it('should return true for date range objects', () => {
      expect(isDateRange({ from: '2024-01-01', to: '2024-01-31' })).toBe(true);
    });

    it('should return false for other types', () => {
      expect(isDateRange('last_30_days')).toBe(false);
      expect(isDateRange(['2024-01-01', '2024-01-31'])).toBe(false);
    });
  });

  describe('isDateRangeTuple', () => {
    it('should return true for date range tuples', () => {
      expect(isDateRangeTuple(['2024-01-01', '2024-01-31'])).toBe(true);
    });

    it('should return false for other types', () => {
      expect(isDateRangeTuple({ from: '2024-01-01', to: '2024-01-31' })).toBe(false);
    });
  });

  describe('isTimeGranularity', () => {
    it('should return true for valid granularities', () => {
      expect(isTimeGranularity(TIME_GRANULARITIES.DAY)).toBe(true);
      expect(isTimeGranularity(TIME_GRANULARITIES.MONTH)).toBe(true);
      expect(isTimeGranularity('day')).toBe(true);
    });

    it('should return false for invalid granularities', () => {
      expect(isTimeGranularity('invalid')).toBe(false);
    });
  });

  describe('resolvePresetDateRange', () => {
    it('should resolve TODAY preset', () => {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const expected = today.toISOString().split('T')[0];

      const result = resolvePresetDateRange(PRESET_DATE_RANGES.TODAY);
      expect(result.from).toBe(expected);
      expect(result.to).toBe(expected);
    });

    it('should resolve LAST_7_DAYS preset', () => {
      const result = resolvePresetDateRange(PRESET_DATE_RANGES.LAST_7_DAYS);
      expect(result.from).toBeDefined();
      expect(result.to).toBeDefined();

      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBe(6); // 7 days inclusive = 6 days difference
    });
  });
});

describe('Join Type Guards', () => {
  describe('isJoinType', () => {
    it('should return true for valid join types', () => {
      expect(isJoinType(JOIN_TYPES.INNER)).toBe(true);
      expect(isJoinType(JOIN_TYPES.LEFT)).toBe(true);
      expect(isJoinType('left')).toBe(true);
    });

    it('should return false for invalid join types', () => {
      expect(isJoinType('invalid')).toBe(false);
    });
  });

  describe('isJoinSpec', () => {
    it('should return true for valid JoinSpec objects', () => {
      const spec = {
        left: 'orders.user_id',
        right: 'users.id',
        type: 'inner',
      };
      expect(isJoinSpec(spec)).toBe(true);
    });

    it('should return false for invalid values', () => {
      expect(isJoinSpec({ table: 'users' })).toBe(false);
      expect(isJoinSpec(null)).toBe(false);
    });
  });
});
