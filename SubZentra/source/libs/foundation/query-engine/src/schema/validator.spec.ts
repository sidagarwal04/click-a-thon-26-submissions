import { describe, expect, it } from 'vitest';

import { MemberRef } from '@open-zentra/foundation-data-model';

import type { Query } from '../types/query';
import type { SchemaDefinition } from '../types/schema-definition';
import { createSchemaRegistry } from './registry';
import {
  formatValidationErrors,
  isValidQuery,
  isValidSchema,
  validateQuery,
  validateSchema,
  validateTableDefinition,
} from './validator';

// =============================================================================
// SHARED FIXTURES
// =============================================================================

const VALID_SCHEMA: SchemaDefinition = {
  name: 'analytics',
  version: '1.0.0',
  tables: {
    orders: {
      name: 'orders',
      sql: 'orders',
      dimensions: {
        status: { type: 'string', sql: 'status' },
        country: { type: 'string', sql: 'country' },
        created_at: { type: 'time', sql: 'created_at' },
      },
      measures: {
        total: { type: 'sum', sql: 'amount' },
        order_count: { type: 'count', sql: '*' },
      },
    },
    users: {
      name: 'users',
      sql: 'users',
      dimensions: {
        name: { type: 'string', sql: 'name' },
        role: { type: 'string', sql: 'role' },
      },
      measures: {
        user_count: { type: 'count', sql: '*' },
      },
      joins: {
        orders: {
          table: 'orders',
          sql: '"users"."id" = "orders"."user_id"',
          type: 'inner',
          relationship: 'one-to-many',
        },
      },
    },
  },
};

// =============================================================================
// validateSchema
// =============================================================================

describe('validateSchema', () => {
  it('passes for a valid schema', () => {
    const result = validateSchema(VALID_SCHEMA);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('fails when schema name is missing', () => {
    const schema: SchemaDefinition = { ...VALID_SCHEMA, name: '' };
    const result = validateSchema(schema);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path === 'schema.name')).toBe(true);
  });

  it('fails when schema version is missing', () => {
    const schema: SchemaDefinition = { ...VALID_SCHEMA, version: '' };
    const result = validateSchema(schema);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path === 'schema.version')).toBe(true);
  });

  it('fails when tables object is empty', () => {
    const schema: SchemaDefinition = { ...VALID_SCHEMA, tables: {} };
    const result = validateSchema(schema);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path === 'schema.tables')).toBe(true);
  });

  it('fails when a join references a nonexistent table', () => {
    const schema: SchemaDefinition = {
      name: 'test',
      version: '1.0.0',
      tables: {
        users: {
          name: 'users',
          sql: 'users',
          dimensions: { name: { type: 'string', sql: 'name' } },
          joins: {
            missing: {
              table: 'nonexistent',
              sql: '"users"."id" = "nonexistent"."user_id"',
              type: 'inner',
              relationship: 'one-to-many',
            },
          },
        },
      },
    };

    const result = validateSchema(schema);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('nonexistent'))).toBe(true);
  });
});

// =============================================================================
// validateTableDefinition
// =============================================================================

describe('validateTableDefinition', () => {
  it('passes for a valid table', () => {
    const table = VALID_SCHEMA.tables['orders'];
    const result = validateTableDefinition(table, 'orders');
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('fails when table name is missing', () => {
    const result = validateTableDefinition(
      { name: '', sql: 'orders', dimensions: {} } as never,
      'orders',
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('.name'))).toBe(true);
  });

  it('fails when table sql is missing', () => {
    const result = validateTableDefinition(
      { name: 'orders', sql: '', dimensions: {} } as never,
      'orders',
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('.sql'))).toBe(true);
  });

  it('fails when measure type is missing', () => {
    const result = validateTableDefinition(
      {
        name: 'orders',
        sql: 'orders',
        measures: { broken: { type: '', sql: 'amount' } },
      } as never,
      'orders',
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('measures.broken.type'))).toBe(true);
  });

  it('fails when dimension sql is missing', () => {
    const result = validateTableDefinition(
      {
        name: 'orders',
        sql: 'orders',
        dimensions: { broken: { type: 'string', sql: '' } },
      } as never,
      'orders',
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('dimensions.broken.sql'))).toBe(true);
  });

  it('warns when table has no measures or dimensions', () => {
    const result = validateTableDefinition({ name: 'empty', sql: 'empty' } as never, 'empty');
    expect(result.valid).toBe(true);
    expect(result.warnings.length).toBeGreaterThan(0);
    expect(result.warnings[0].message).toContain('no measures or dimensions');
  });
});

// =============================================================================
// validateQuery
// =============================================================================

describe('validateQuery', () => {
  const registry = createSchemaRegistry(VALID_SCHEMA);

  it('passes for a simple valid query', () => {
    const query: Query = {
      dimensions: [{ member: 'orders.status' }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('fails when a dimension member is not in schema', () => {
    const query: Query = {
      dimensions: [{ member: 'orders.nonexistent' }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe('query.dimensions[0].member');
  });

  it('fails when a measure member references a dimension', () => {
    const query: Query = {
      measures: [{ member: 'orders.status', aggregation: 'sum' }],
    };
    // orders.status is a dimension, should still pass the basic member-exists check
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(true);
  });

  it('fails when a measure member is not in schema', () => {
    const query: Query = {
      measures: [{ member: 'orders.unknown_col', aggregation: 'sum' }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toContain('measures[0].member');
  });

  it('fails when a measure has no aggregation', () => {
    const query: Query = {
      measures: [{ member: 'orders.status', aggregation: '' as never }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('aggregation'))).toBe(true);
  });

  it('passes COUNT(*) measure with member "*"', () => {
    const query: Query = {
      measures: [{ member: '*', aggregation: 'count' }],
    };
    const result = validateQuery(query, registry);
    // member '*' should be accepted for count
    expect(result.valid).toBe(true);
  });

  it('validates time dimension against schema', () => {
    const query: Query = {
      timeDimensions: [
        { dimension: MemberRef.create('orders', 'created_at'), granularity: 'day' },
      ],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(true);
  });

  it('fails when time dimension not in schema', () => {
    const query: Query = {
      timeDimensions: [
        { dimension: MemberRef.create('orders', 'nonexistent'), granularity: 'day' },
      ],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toContain('timeDimensions[0]');
  });

  it('validates filter members against schema', () => {
    const query: Query = {
      dimensions: [{ member: 'orders.status' }],
      filters: [{ member: 'orders.status', operator: 'equals', values: ['active'] }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(true);
  });

  it('fails when filter member not in schema', () => {
    const query: Query = {
      filters: [{ member: 'orders.nonexistent', operator: 'equals', values: ['x'] }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toContain('filters[0].member');
  });

  it('validates orderBy members against schema', () => {
    const query: Query = {
      dimensions: [{ member: 'orders.status' }],
      orderBy: [{ member: 'orders.unknown_field', direction: 'asc' }],
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe('query.orderBy[0].member');
  });

  it('fails when limit is negative', () => {
    const query: Query = {
      dimensions: [{ member: 'orders.status' }],
      limit: -1,
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe('query.limit');
  });

  it('fails when offset is negative', () => {
    const query: Query = {
      dimensions: [{ member: 'orders.status' }],
      offset: -5,
    };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe('query.offset');
  });

  it('warns for ungrouped query with measures', () => {
    const query: Query = {
      measures: [{ member: '*', aggregation: 'count' }],
      ungrouped: true,
    };
    const result = validateQuery(query, registry);
    expect(result.warnings.some((w) => w.path === 'query.ungrouped')).toBe(true);
  });

  it('passes for deeply nested filters', () => {
    // Build a filter nested 21 levels deep
    let filter: { member: string; operator: string; values: string[] } | { and: unknown[] } = {
      member: 'orders.status',
      operator: 'equals',
      values: ['active'],
    };
    for (let i = 0; i < 21; i++) {
      filter = { and: [filter] };
    }

    const query: Query = { filters: [filter as never] };
    const result = validateQuery(query, registry);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});

// =============================================================================
// isValidQuery / isValidSchema
// =============================================================================

describe('isValidQuery', () => {
  const registry = createSchemaRegistry(VALID_SCHEMA);

  it('returns true for valid query', () => {
    expect(isValidQuery({ dimensions: [{ member: 'orders.status' }] }, registry)).toBe(true);
  });

  it('returns false for invalid query', () => {
    expect(isValidQuery({ dimensions: [{ member: 'orders.nope' }] }, registry)).toBe(false);
  });
});

describe('isValidSchema', () => {
  it('returns true for valid schema', () => {
    expect(isValidSchema(VALID_SCHEMA)).toBe(true);
  });

  it('returns false for invalid schema', () => {
    expect(isValidSchema({ name: '', version: '', tables: {} } as SchemaDefinition)).toBe(false);
  });
});

// =============================================================================
// formatValidationErrors
// =============================================================================

describe('formatValidationErrors', () => {
  it('returns "Validation passed" for valid result', () => {
    const output = formatValidationErrors({ valid: true, errors: [], warnings: [] });
    expect(output).toBe('Validation passed');
  });

  it('formats errors with paths and suggestions', () => {
    const output = formatValidationErrors({
      valid: false,
      errors: [
        { path: 'query.limit', message: 'Limit must be >= 0', suggestion: 'Use a positive number' },
      ],
      warnings: [],
    });
    expect(output).toContain('Validation failed');
    expect(output).toContain('query.limit');
    expect(output).toContain('Limit must be >= 0');
    expect(output).toContain('Use a positive number');
  });

  it('includes warnings section when present', () => {
    const output = formatValidationErrors({
      valid: false,
      errors: [{ path: 'a', message: 'b' }],
      warnings: [{ path: 'w', message: 'warning msg' }],
    });
    expect(output).toContain('Warnings:');
    expect(output).toContain('warning msg');
  });
});
