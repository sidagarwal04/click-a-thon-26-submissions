import { afterEach, describe, expect, it } from 'vitest';

import type { Query } from '../types/query';
import {
  createTableExtractor,
  extractTables,
  getPrimaryTable,
  getTableExtractor,
  resetTableExtractor,
  TableExtractor,
} from './table-extractor';

// =============================================================================
// TableExtractor
// =============================================================================

describe('TableExtractor', () => {
  const extractor = new TableExtractor();

  // ───────────────────────────────────────────────────────────────────────────
  // extract
  // ───────────────────────────────────────────────────────────────────────────

  describe('extract', () => {
    it('extracts tables from dimensions', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'users.name' }, { member: 'orders.status' }],
      };
      expect(extractor.extract(query)).toEqual(['users', 'orders']);
    });

    it('extracts tables from measures', () => {
      const query: Partial<Query> = {
        measures: [{ member: 'orders.amount', aggregation: 'sum' }],
      };
      expect(extractor.extract(query)).toEqual(['orders']);
    });

    it('extracts tables from filters', () => {
      const query: Partial<Query> = {
        filters: [{ member: 'products.price', operator: 'gte', values: [100] }],
      };
      expect(extractor.extract(query)).toEqual(['products']);
    });

    it('extracts tables from joins', () => {
      const query: Partial<Query> = {
        joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],
      };
      expect(extractor.extract(query)).toEqual(['orders', 'users']);
    });

    it('extracts tables from orderBy', () => {
      const query: Partial<Query> = {
        orderBy: [{ member: 'users.created_at', direction: 'desc' }],
      };
      expect(extractor.extract(query)).toEqual(['users']);
    });

    it('deduplicates tables', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'users.name' }],
        filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
      };
      expect(extractor.extract(query)).toEqual(['users']);
    });

    it('returns empty array for empty query', () => {
      expect(extractor.extract({})).toEqual([]);
    });

    it('handles members without table prefix (returns empty)', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'invalid_no_dot' }],
      };
      expect(extractor.extract(query)).toEqual([]);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // extractDetailed
  // ───────────────────────────────────────────────────────────────────────────

  describe('extractDetailed', () => {
    it('provides per-source breakdowns', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'users.name' }],
        measures: [{ member: 'orders.amount', aggregation: 'sum' }],
        filters: [{ member: 'products.status', operator: 'equals', values: ['active'] }],
        joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],
        orderBy: [{ member: 'users.created_at', direction: 'asc' }],
      };

      const result = extractor.extractDetailed(query);

      expect(result.tables).toContain('users');
      expect(result.tables).toContain('orders');
      expect(result.tables).toContain('products');
      expect(result.primaryTable).toBe('users'); // first from dimensions
      expect(result.fromDimensions).toEqual(['users']);
      expect(result.fromMeasures).toEqual(['orders']);
      expect(result.fromFilters).toEqual(['products']);
      expect(result.fromJoins).toEqual(['orders', 'users']);
      expect(result.fromOrderBy).toEqual(['users']);
      expect(result.hasTable).toBe(true);
      expect(result.hasMultipleTables).toBe(true);
    });

    it('handles nested filter groups (AND)', () => {
      const query: Partial<Query> = {
        filters: [
          {
            and: [
              { member: 'users.status', operator: 'equals', values: ['active'] },
              { member: 'orders.total', operator: 'gte', values: [100] },
            ],
          },
        ],
      };
      const result = extractor.extractDetailed(query);
      expect(result.fromFilters).toContain('users');
      expect(result.fromFilters).toContain('orders');
    });

    it('handles nested filter groups (OR)', () => {
      const query: Partial<Query> = {
        filters: [
          {
            or: [
              { member: 'users.role', operator: 'equals', values: ['admin'] },
              { member: 'users.role', operator: 'equals', values: ['superuser'] },
            ],
          },
        ],
      };
      const result = extractor.extractDetailed(query);
      expect(result.fromFilters).toEqual(['users']);
    });

    it('returns hasTable false for empty query', () => {
      const result = extractor.extractDetailed({});
      expect(result.hasTable).toBe(false);
      expect(result.primaryTable).toBeNull();
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // getPrimaryTable
  // ───────────────────────────────────────────────────────────────────────────

  describe('getPrimaryTable', () => {
    it('returns the first table from dimensions', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'orders.status' }],
        measures: [{ member: 'users.id', aggregation: 'count' }],
      };
      expect(extractor.getPrimaryTable(query)).toBe('orders');
    });

    it('returns null for empty query', () => {
      expect(extractor.getPrimaryTable({})).toBeNull();
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // hasMultipleTables
  // ───────────────────────────────────────────────────────────────────────────

  describe('hasMultipleTables', () => {
    it('returns false for single-table query', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'users.name' }],
      };
      expect(extractor.hasMultipleTables(query)).toBe(false);
    });

    it('returns true for multi-table query', () => {
      const query: Partial<Query> = {
        dimensions: [{ member: 'users.name' }],
        measures: [{ member: 'orders.amount', aggregation: 'sum' }],
      };
      expect(extractor.hasMultipleTables(query)).toBe(true);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // extractFromMeasures — measure filter tables
  // ───────────────────────────────────────────────────────────────────────────

  describe('extractFromMeasures', () => {
    it('includes tables from measure filters', () => {
      const tables = extractor.extractFromMeasures([
        {
          member: 'orders.amount',
          aggregation: 'sum',
          filter: { member: 'products.status', operator: 'equals', values: ['active'] },
        },
      ]);
      expect(tables).toContain('orders');
      expect(tables).toContain('products');
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // extractFromJoins — additional conditions
  // ───────────────────────────────────────────────────────────────────────────

  describe('extractFromJoins', () => {
    it('includes tables from additional join conditions', () => {
      const tables = extractor.extractFromJoins([
        {
          left: 'orders.user_id',
          right: 'users.id',
          type: 'inner',
          additionalConditions: [{ left: 'orders.company_id', right: 'companies.id' }],
        },
      ]);
      expect(tables).toContain('orders');
      expect(tables).toContain('users');
      expect(tables).toContain('companies');
    });
  });
});

// =============================================================================
// Factory & Singleton helpers
// =============================================================================

describe('createTableExtractor', () => {
  it('creates a new instance', () => {
    const a = createTableExtractor();
    const b = createTableExtractor();
    expect(a).not.toBe(b);
  });
});

describe('getTableExtractor / resetTableExtractor', () => {
  afterEach(async () => {
    await resetTableExtractor();
  });

  it('returns the same singleton instance', () => {
    const a = getTableExtractor();
    const b = getTableExtractor();
    expect(a).toBe(b);
  });

  it('provides a new instance after reset', async () => {
    const a = getTableExtractor();
    await resetTableExtractor();
    const b = getTableExtractor();
    expect(a).not.toBe(b);
  });
});

// =============================================================================
// Standalone utilities
// =============================================================================

describe('extractTables (standalone)', () => {
  it('delegates to singleton', () => {
    const tables = extractTables({ dimensions: [{ member: 'users.name' }] });
    expect(tables).toEqual(['users']);
  });
});

describe('getPrimaryTable (standalone)', () => {
  it('delegates to singleton', () => {
    expect(getPrimaryTable({ dimensions: [{ member: 'orders.id' }] })).toBe('orders');
  });

  it('returns null for empty query', () => {
    expect(getPrimaryTable({})).toBeNull();
  });
});
