/**
 * SQL Compiler Tests
 *
 * @module compiler/sql-compiler.spec
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { AGGREGATIONS } from '../types/aggregation';
import { FILTER_OPERATORS } from '../types/filter';
import { JOIN_TYPES } from '../types/join';
import { ORDER_DIRECTIONS } from '../types/order';
import type { Query } from '../types/query';
import { SqlCompiler } from './sql-compiler';
import {
  buildAggregation,
  buildCaseExpression,
  buildContainsPattern,
  buildDateTrunc,
  buildEndsWithPattern,
  buildStartsWithPattern,
  escapeLikePattern,
  escapeString,
  formatSql,
  formatValue,
  formatValueList,
  isValidIdentifier,
  quoteColumn,
  quoteIdentifier,
  quoteMemberRef,
  quoteTableName,
  sanitizeIdentifier,
} from './sql-utils';

describe('SqlCompiler', () => {
  let compiler: SqlCompiler;

  beforeEach(() => {
    compiler = new SqlCompiler();
  });

  describe('constructor', () => {
    it('should create compiler with default config', () => {
      const compiler = new SqlCompiler();
      expect(compiler).toBeInstanceOf(SqlCompiler);
      expect(compiler.getConfig().dialect).toBe('duckdb');
    });

    it('should create compiler with custom config', () => {
      const compiler = new SqlCompiler({
        dialect: 'duckdb',
        quoteStyle: 'double',
        prettyPrint: true,
      });
      expect(compiler.getConfig().prettyPrint).toBe(true);
      expect(compiler.getConfig().quoteStyle).toBe('double');
    });
  });

  describe('compile', () => {
    describe('SELECT clause', () => {
      it('should compile empty query as SELECT table.*', () => {
        const result = compiler.compile({}, { primaryTable: 'orders' });

        expect(result.sql).toContain('SELECT "orders".*');
        expect(result.hasAggregations).toBe(false);
      });

      it('should compile dimensions (DimensionSpec format)', () => {
        const query: Query = {
          dimensions: [{ member: 'orders.status' }, { member: 'orders.region' }],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('"orders"."status"');
        expect(result.sql).toContain('"orders"."region"');
      });

      it('should compile measures with aggregation (MeasureSpec format)', () => {
        const query: Query = {
          measures: [
            {
              member: 'orders.amount',
              aggregation: AGGREGATIONS.SUM,
              alias: 'total_amount',
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('SUM("orders"."amount")');
        expect(result.sql).toContain('AS "total_amount"');
        expect(result.hasAggregations).toBe(true);
      });

      it('should compile COUNT(*) measure', () => {
        const query: Query = {
          measures: [
            {
              member: '*',
              aggregation: AGGREGATIONS.COUNT,
              alias: 'count',
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        // The compiler quotes the * as an identifier
        expect(result.sql).toContain('COUNT(');
        expect(result.sql).toContain('AS "count"');
      });

      it('should compile COUNT DISTINCT measure', () => {
        const query: Query = {
          measures: [
            {
              member: 'orders.user_id',
              aggregation: AGGREGATIONS.COUNT,
              alias: 'unique_users',
              distinct: true,
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('COUNT(DISTINCT');
      });
    });

    describe('FROM clause', () => {
      it('should compile FROM with table name', () => {
        const result = compiler.compile({}, { primaryTable: 'orders' });

        expect(result.sql).toContain('FROM "orders"');
        expect(result.tables).toContain('orders');
      });

      it('should extract table from dimensions', () => {
        const query: Query = {
          dimensions: [{ member: 'orders.status' }],
        };

        const result = compiler.compile(query);

        expect(result.tables).toContain('orders');
      });
    });

    describe('JOIN clause', () => {
      it('should compile inner join (JoinSpec format)', () => {
        const query: Query = {
          joins: [
            {
              left: 'orders.user_id',
              right: 'users.id',
              type: JOIN_TYPES.INNER,
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('INNER JOIN "users"');
        expect(result.sql).toContain('"orders"."user_id" = "users"."id"');
        expect(result.tables).toContain('users');
      });

      it('should compile left join', () => {
        const query: Query = {
          joins: [
            {
              left: 'orders.user_id',
              right: 'users.id',
              type: JOIN_TYPES.LEFT,
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('LEFT OUTER JOIN "users"');
      });

      it('should compile multiple joins', () => {
        const query: Query = {
          joins: [
            { left: 'orders.user_id', right: 'users.id', type: JOIN_TYPES.INNER },
            { left: 'orders.product_id', right: 'products.id', type: JOIN_TYPES.LEFT },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('INNER JOIN "users"');
        expect(result.sql).toContain('LEFT OUTER JOIN "products"');
        expect(result.tables).toContain('users');
        expect(result.tables).toContain('products');
      });
    });

    describe('WHERE clause', () => {
      it('should compile equals filter (FilterCondition format)', () => {
        const query: Query = {
          filters: [
            {
              member: 'orders.status',
              operator: FILTER_OPERATORS.EQUALS,
              values: ['completed'],
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('WHERE "orders"."status" = \'completed\'');
      });

      it('should compile comparison filters', () => {
        const query: Query = {
          filters: [
            {
              member: 'orders.amount',
              operator: FILTER_OPERATORS.GT,
              values: [100],
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('"orders"."amount" > 100');
      });

      it('should compile IN filter', () => {
        const query: Query = {
          filters: [
            {
              member: 'orders.status',
              operator: FILTER_OPERATORS.IN,
              values: ['pending', 'processing', 'completed'],
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain("IN ('pending', 'processing', 'completed')");
      });

      it('should compile NULL check filters', () => {
        const query: Query = {
          filters: [
            {
              member: 'orders.cancelled_at',
              operator: FILTER_OPERATORS.IS_NULL,
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('"orders"."cancelled_at" IS NULL');
      });

      it('should compile LIKE filters', () => {
        const query: Query = {
          filters: [
            {
              member: 'users.email',
              operator: FILTER_OPERATORS.CONTAINS,
              values: ['@example.com'],
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'users' });

        expect(result.sql).toContain('LIKE');
        expect(result.sql).toContain('%@example.com%');
      });

      it('should compile logical AND filter', () => {
        const query: Query = {
          filters: [
            {
              and: [
                {
                  member: 'orders.status',
                  operator: FILTER_OPERATORS.EQUALS,
                  values: ['completed'],
                },
                { member: 'orders.amount', operator: FILTER_OPERATORS.GT, values: [100] },
              ],
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('AND');
      });

      it('should compile logical OR filter', () => {
        const query: Query = {
          filters: [
            {
              or: [
                { member: 'orders.status', operator: FILTER_OPERATORS.EQUALS, values: ['pending'] },
                {
                  member: 'orders.status',
                  operator: FILTER_OPERATORS.EQUALS,
                  values: ['processing'],
                },
              ],
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('OR');
      });
    });

    describe('GROUP BY clause', () => {
      it('should compile GROUP BY for dimensions with measures', () => {
        const query: Query = {
          dimensions: [{ member: 'orders.status' }],
          measures: [
            {
              member: 'orders.amount',
              aggregation: AGGREGATIONS.SUM,
              alias: 'total',
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('GROUP BY "orders"."status"');
      });
    });

    describe('ORDER BY clause', () => {
      it('should compile ORDER BY ascending', () => {
        const query: Query = {
          dimensions: [{ member: 'orders.status' }],
          orderBy: [
            {
              member: 'orders.status',
              direction: ORDER_DIRECTIONS.ASC,
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('ORDER BY "orders"."status" ASC');
      });

      it('should compile ORDER BY descending', () => {
        const query: Query = {
          dimensions: [{ member: 'orders.amount' }],
          orderBy: [
            {
              member: 'orders.amount',
              direction: ORDER_DIRECTIONS.DESC,
            },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('ORDER BY "orders"."amount" DESC');
      });

      it('should compile multiple ORDER BY clauses', () => {
        const query: Query = {
          orderBy: [
            { member: 'orders.status', direction: ORDER_DIRECTIONS.ASC },
            { member: 'orders.amount', direction: ORDER_DIRECTIONS.DESC },
          ],
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('ORDER BY');
        expect(result.sql).toContain('"orders"."status" ASC');
        expect(result.sql).toContain('"orders"."amount" DESC');
      });
    });

    describe('LIMIT/OFFSET', () => {
      it('should compile LIMIT', () => {
        const query: Query = {
          limit: 100,
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('LIMIT 100');
      });

      it('should compile OFFSET', () => {
        const query: Query = {
          offset: 50,
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('OFFSET 50');
      });

      it('should compile both LIMIT and OFFSET', () => {
        const query: Query = {
          limit: 100,
          offset: 50,
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('LIMIT 100');
        expect(result.sql).toContain('OFFSET 50');
      });

      it('should not include OFFSET 0', () => {
        const query: Query = {
          limit: 100,
          offset: 0,
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('LIMIT 100');
        expect(result.sql).not.toContain('OFFSET');
      });
    });

    describe('complex queries', () => {
      it('should compile a complete analytical query', () => {
        const query: Query = {
          dimensions: [{ member: 'orders.status' }],
          measures: [
            {
              member: 'orders.amount',
              aggregation: AGGREGATIONS.SUM,
              alias: 'total_amount',
            },
            {
              member: '*',
              aggregation: AGGREGATIONS.COUNT,
              alias: 'order_count',
            },
          ],
          filters: [
            {
              member: 'orders.amount',
              operator: FILTER_OPERATORS.GT,
              values: [0],
            },
          ],
          joins: [
            {
              left: 'orders.user_id',
              right: 'users.id',
              type: JOIN_TYPES.LEFT,
            },
          ],
          orderBy: [{ member: 'total_amount', direction: ORDER_DIRECTIONS.DESC }],
          limit: 10,
        };

        const result = compiler.compile(query, { primaryTable: 'orders' });

        expect(result.sql).toContain('SELECT');
        expect(result.sql).toContain('FROM "orders"');
        expect(result.sql).toContain('LEFT OUTER JOIN "users"');
        expect(result.sql).toContain('WHERE');
        expect(result.sql).toContain('GROUP BY');
        expect(result.sql).toContain('ORDER BY');
        expect(result.sql).toContain('LIMIT 10');
        expect(result.hasAggregations).toBe(true);
        expect(result.tables).toContain('orders');
        expect(result.tables).toContain('users');
      });
    });
  });

  describe('compileCount', () => {
    it('should compile a COUNT query', () => {
      const sql = compiler.compileCount('orders');
      expect(sql).toContain('SELECT COUNT(*)');
      expect(sql).toContain('FROM "orders"');
    });
  });

  describe('compileSelectAll', () => {
    it('should compile SELECT * query', () => {
      const sql = compiler.compileSelectAll('orders');
      expect(sql).toContain('SELECT *');
      expect(sql).toContain('FROM "orders"');
    });

    it('should add LIMIT', () => {
      const sql = compiler.compileSelectAll('orders', 100);
      expect(sql).toContain('LIMIT 100');
    });

    it('should add OFFSET', () => {
      const sql = compiler.compileSelectAll('orders', 100, 50);
      expect(sql).toContain('OFFSET 50');
    });
  });
});

describe('SQL Utilities', () => {
  describe('quoteIdentifier', () => {
    it('should quote simple identifier', () => {
      expect(quoteIdentifier('users')).toBe('"users"');
    });

    it('should escape double quotes in identifier', () => {
      expect(quoteIdentifier('user"name')).toBe('"user""name"');
    });
  });

  describe('quoteTableName', () => {
    it('should quote table name without schema', () => {
      expect(quoteTableName('users')).toBe('"users"');
    });

    it('should quote table name with schema', () => {
      expect(quoteTableName('users', 'public')).toBe('"public"."users"');
    });
  });

  describe('quoteColumn', () => {
    it('should quote column without table alias', () => {
      expect(quoteColumn('name')).toBe('"name"');
    });

    it('should quote column with table alias', () => {
      expect(quoteColumn('name', 'u')).toBe('"u"."name"');
    });
  });

  describe('quoteMemberRef', () => {
    it('should quote table.column reference', () => {
      expect(quoteMemberRef('users.name')).toBe('"users"."name"');
    });

    it('should quote single identifier', () => {
      expect(quoteMemberRef('name')).toBe('"name"');
    });
  });

  describe('escapeString', () => {
    it('should escape single quotes', () => {
      expect(escapeString("it's")).toBe("it''s");
    });

    it('should escape multiple single quotes', () => {
      expect(escapeString("it's John's")).toBe("it''s John''s");
    });
  });

  describe('formatValue', () => {
    it('should format null', () => {
      expect(formatValue(null)).toBe('NULL');
    });

    it('should format string', () => {
      expect(formatValue('hello')).toBe("'hello'");
    });

    it('should format string with quotes', () => {
      expect(formatValue("it's")).toBe("'it''s'");
    });

    it('should format number', () => {
      expect(formatValue(42)).toBe('42');
    });

    it('should format boolean true', () => {
      expect(formatValue(true)).toBe('TRUE');
    });

    it('should format boolean false', () => {
      expect(formatValue(false)).toBe('FALSE');
    });

    it('should format Date', () => {
      const date = new Date('2024-01-15T00:00:00.000Z');
      expect(formatValue(date)).toContain('2024-01-15');
    });
  });

  describe('formatValueList', () => {
    it('should format list of values', () => {
      expect(formatValueList(['a', 'b', 'c'])).toBe("'a', 'b', 'c'");
    });

    it('should format mixed types', () => {
      expect(formatValueList(['a', 1, true])).toBe("'a', 1, TRUE");
    });
  });

  describe('escapeLikePattern', () => {
    it('should escape percent sign', () => {
      expect(escapeLikePattern('100%')).toBe('100\\%');
    });

    it('should escape underscore', () => {
      expect(escapeLikePattern('user_name')).toBe('user\\_name');
    });

    it('should escape backslash', () => {
      expect(escapeLikePattern('path\\to')).toBe('path\\\\to');
    });
  });

  describe('buildContainsPattern', () => {
    it('should build contains pattern', () => {
      expect(buildContainsPattern('test')).toBe("'%test%'");
    });

    it('should escape special characters', () => {
      expect(buildContainsPattern('100%')).toBe("'%100\\%%'");
    });
  });

  describe('buildStartsWithPattern', () => {
    it('should build starts with pattern', () => {
      expect(buildStartsWithPattern('test')).toBe("'test%'");
    });
  });

  describe('buildEndsWithPattern', () => {
    it('should build ends with pattern', () => {
      expect(buildEndsWithPattern('test')).toBe("'%test'");
    });
  });

  describe('buildDateTrunc', () => {
    it('should build date_trunc expression', () => {
      expect(buildDateTrunc('month', '"orders"."created_at"')).toBe(
        'date_trunc(\'month\', "orders"."created_at")',
      );
    });
  });

  describe('buildAggregation', () => {
    it('should build simple aggregation', () => {
      expect(buildAggregation('SUM', '"amount"')).toBe('SUM("amount")');
    });

    it('should build COUNT(*)', () => {
      expect(buildAggregation('COUNT', '*')).toBe('COUNT(*)');
    });

    it('should build aggregation with DISTINCT', () => {
      expect(buildAggregation('SUM', '"amount"', true)).toBe('SUM(DISTINCT "amount")');
    });

    it('should build COUNT DISTINCT', () => {
      expect(buildAggregation('COUNT(DISTINCT', '"user_id"')).toBe('COUNT(DISTINCT "user_id")');
    });

    it('should build aggregation with filter', () => {
      expect(buildAggregation('SUM', '"amount"', false, '"status" = \'completed\'')).toBe(
        'SUM("amount") FILTER (WHERE "status" = \'completed\')',
      );
    });
  });

  describe('buildCaseExpression', () => {
    it('should build CASE expression without ELSE', () => {
      const result = buildCaseExpression([
        { when: 'status = 1', then: "'active'" },
        { when: 'status = 0', then: "'inactive'" },
      ]);
      expect(result).toBe("CASE WHEN status = 1 THEN 'active' WHEN status = 0 THEN 'inactive' END");
    });

    it('should build CASE expression with ELSE', () => {
      const result = buildCaseExpression([{ when: 'status = 1', then: "'active'" }], "'unknown'");
      expect(result).toBe("CASE WHEN status = 1 THEN 'active' ELSE 'unknown' END");
    });
  });

  describe('isValidIdentifier', () => {
    it('should return true for valid identifiers', () => {
      expect(isValidIdentifier('users')).toBe(true);
      expect(isValidIdentifier('_private')).toBe(true);
      expect(isValidIdentifier('user123')).toBe(true);
    });

    it('should return false for invalid identifiers', () => {
      expect(isValidIdentifier('123users')).toBe(false);
      expect(isValidIdentifier('user-name')).toBe(false);
      expect(isValidIdentifier('user.name')).toBe(false);
    });
  });

  describe('sanitizeIdentifier', () => {
    it('should replace invalid characters', () => {
      expect(sanitizeIdentifier('user-name')).toBe('user_name');
      expect(sanitizeIdentifier('user.name')).toBe('user_name');
      expect(sanitizeIdentifier('user name')).toBe('user_name');
    });
  });

  describe('formatSql', () => {
    it('should normalize whitespace', () => {
      expect(formatSql('SELECT  *   FROM   users')).toBe('SELECT * FROM users');
    });

    it('should pretty print when enabled', () => {
      const sql = 'SELECT * FROM users WHERE id = 1';
      const result = formatSql(sql, true);
      expect(result).toContain('\n');
    });
  });
});
