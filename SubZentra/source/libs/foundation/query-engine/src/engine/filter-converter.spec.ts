import { describe, expect, it } from 'vitest';

import type { Query } from '../types/query';
import {
  convertFiltersToArgs,
  countConvertibleFilters,
  hasComplexFilters,
} from './filter-converter';

// =============================================================================
// convertFiltersToArgs
// =============================================================================

describe('convertFiltersToArgs', () => {
  it('returns empty object for query with no filters', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
    };
    expect(convertFiltersToArgs(query)).toEqual({});
  });

  it('includes limit and offset from query', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      limit: 10,
      offset: 20,
    };
    const args = convertFiltersToArgs(query);
    expect(args).toEqual({ limit: 10, offset: 20 });
  });

  it('converts simple equality filters to args', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [
        { member: 'users.status', operator: 'equals', values: ['active'] },
        { member: 'users.role', operator: 'equals', values: ['admin'] },
      ],
    };
    const args = convertFiltersToArgs(query);
    expect(args).toEqual({ status: 'active', role: 'admin' });
  });

  it('ignores non-equality filters', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [
        { member: 'users.age', operator: 'gte', values: [18] },
        { member: 'users.status', operator: 'equals', values: ['active'] },
      ],
    };
    const args = convertFiltersToArgs(query);
    expect(args).toEqual({ status: 'active' });
    expect(args).not.toHaveProperty('age');
  });

  it('ignores equality filters with multiple values', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [{ member: 'users.status', operator: 'equals', values: ['active', 'pending'] }],
    };
    const args = convertFiltersToArgs(query);
    expect(args).toEqual({});
  });

  it('ignores filter groups (AND/OR)', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [
        {
          and: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
        },
      ],
    };
    const args = convertFiltersToArgs(query);
    // Groups are not convertible
    expect(args).toEqual({});
  });

  it('combines pagination with filters', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      limit: 50,
      filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
    };
    const args = convertFiltersToArgs(query);
    expect(args).toEqual({ limit: 50, status: 'active' });
  });
});

// =============================================================================
// hasComplexFilters
// =============================================================================

describe('hasComplexFilters', () => {
  it('returns false for query with no filters', () => {
    const query: Query = { dimensions: [{ member: 'users.name' }] };
    expect(hasComplexFilters(query)).toBe(false);
  });

  it('returns false when all filters are simple equality', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
    };
    expect(hasComplexFilters(query)).toBe(false);
  });

  it('returns true for comparison operator', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [{ member: 'users.age', operator: 'gte', values: [18] }],
    };
    expect(hasComplexFilters(query)).toBe(true);
  });

  it('returns true for string operator', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [{ member: 'users.name', operator: 'contains', values: ['john'] }],
    };
    expect(hasComplexFilters(query)).toBe(true);
  });

  it('returns true for filter groups', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [
        {
          or: [
            { member: 'users.status', operator: 'equals', values: ['active'] },
            { member: 'users.status', operator: 'equals', values: ['pending'] },
          ],
        },
      ],
    };
    expect(hasComplexFilters(query)).toBe(true);
  });
});

// =============================================================================
// countConvertibleFilters
// =============================================================================

describe('countConvertibleFilters', () => {
  it('returns 0 for query with no filters', () => {
    const query: Query = { dimensions: [{ member: 'users.name' }] };
    expect(countConvertibleFilters(query)).toBe(0);
  });

  it('counts convertible equality filters', () => {
    const query: Query = {
      dimensions: [{ member: 'users.name' }],
      filters: [
        { member: 'users.status', operator: 'equals', values: ['active'] },
        { member: 'users.role', operator: 'equals', values: ['admin'] },
        { member: 'users.age', operator: 'gte', values: [18] },
      ],
    };
    expect(countConvertibleFilters(query)).toBe(2);
  });
});
