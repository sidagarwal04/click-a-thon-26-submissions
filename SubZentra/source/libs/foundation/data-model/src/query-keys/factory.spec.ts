/**
 * Query Key Factory Tests
 *
 * Tests for query key creation, hashing, pattern matching,
 * metadata extraction, and pre-defined factories.
 */

import { describe, expect, it } from 'vitest';

import {
  createAnalyticsQueryKey,
  createQueryKeys,
  dashboardKeys,
  eventKeys,
  extractQueryKeyMeta,
  hashQueryKey,
  matchesQueryKey,
  projectKeys,
  reportKeys,
  sessionKeys,
  tenantKeys,
  userKeys,
} from './factory';

// =============================================================================
// createQueryKeys
// =============================================================================

describe('createQueryKeys', () => {
  const keys = createQueryKeys<'users'>('users');

  describe('.all', () => {
    it('should return entity root key', () => {
      expect(keys.all).toEqual(['users']);
    });
  });

  describe('.list', () => {
    it('should return list key without filters', () => {
      expect(keys.list()).toEqual(['users', 'list']);
    });

    it('should include filters when provided', () => {
      const result = keys.list({ status: 'active' });
      expect(result).toEqual(['users', 'list', { status: 'active' }]);
    });

    it('should omit empty filters', () => {
      expect(keys.list({})).toEqual(['users', 'list']);
    });
  });

  describe('.detail', () => {
    it('should return detail key with id', () => {
      expect(keys.detail('user-123')).toEqual(['users', 'detail', 'user-123']);
    });
  });

  describe('.infinite', () => {
    it('should return infinite key without filters', () => {
      expect(keys.infinite()).toEqual(['users', 'infinite']);
    });

    it('should include filters when provided', () => {
      const result = keys.infinite({ cursor: 'abc' });
      expect(result).toEqual(['users', 'infinite', { cursor: 'abc' }]);
    });
  });
});

// =============================================================================
// createAnalyticsQueryKey
// =============================================================================

describe('createAnalyticsQueryKey', () => {
  it('should create key for single table', () => {
    const key = createAnalyticsQueryKey('events', 'countByType');
    expect(key[0]).toBe('analytics');
    expect(key[1]).toBe('tables:events');
    expect(key[2]).toBe('query:countByType');
  });

  it('should create key for multiple tables (sorted)', () => {
    const key = createAnalyticsQueryKey(['sessions', 'events'], 'join');
    expect(key[1]).toBe('tables:events,sessions');
  });

  it('should include params when provided', () => {
    const key = createAnalyticsQueryKey('events', 'timeSeries', { granularity: 'day' });
    expect(key).toHaveLength(4);
    expect(key[3]).toEqual({ granularity: 'day' });
  });

  it('should omit empty params', () => {
    const key = createAnalyticsQueryKey('events', 'count', {});
    expect(key).toHaveLength(3);
  });
});

// =============================================================================
// extractQueryKeyMeta
// =============================================================================

describe('extractQueryKeyMeta', () => {
  it('should extract entity list metadata', () => {
    const meta = extractQueryKeyMeta(['users', 'list']);
    expect(meta.entity).toBe('users');
    expect(meta.scope).toBe('list');
    expect(meta.isAnalytics).toBe(false);
  });

  it('should extract entity detail metadata', () => {
    const meta = extractQueryKeyMeta(['users', 'detail', 'user-1']);
    expect(meta.entity).toBe('users');
    expect(meta.scope).toBe('detail');
  });

  it('should extract analytics metadata', () => {
    const meta = extractQueryKeyMeta(['analytics', 'tables:events', 'query:count']);
    expect(meta.entity).toBe('analytics');
    expect(meta.isAnalytics).toBe(true);
    expect(meta.tables).toEqual(['events']);
  });

  it('should parse multiple tables from analytics key', () => {
    const meta = extractQueryKeyMeta(['analytics', 'tables:events,sessions', 'query:join']);
    expect(meta.tables).toEqual(['events', 'sessions']);
  });

  it('should handle root-only key', () => {
    const meta = extractQueryKeyMeta(['users']);
    expect(meta.entity).toBe('users');
    expect(meta.scope).toBeUndefined();
  });
});

// =============================================================================
// hashQueryKey
// =============================================================================

describe('hashQueryKey', () => {
  it('should produce a hex string', () => {
    const hash = hashQueryKey(['users', 'list']);
    expect(hash).toMatch(/^[0-9a-f]+$/);
  });

  it('should be deterministic', () => {
    const a = hashQueryKey(['users', 'list', { status: 'active' }]);
    const b = hashQueryKey(['users', 'list', { status: 'active' }]);
    expect(a).toBe(b);
  });

  it('should produce different hashes for different keys', () => {
    const a = hashQueryKey(['users', 'list']);
    const b = hashQueryKey(['events', 'list']);
    expect(a).not.toBe(b);
  });

  it('should produce same hash regardless of object key order', () => {
    const a = hashQueryKey(['users', 'list', { a: 1, b: 2 }]);
    const b = hashQueryKey(['users', 'list', { b: 2, a: 1 }]);
    expect(a).toBe(b);
  });
});

// =============================================================================
// matchesQueryKey
// =============================================================================

describe('matchesQueryKey', () => {
  it('should match exact keys', () => {
    expect(matchesQueryKey(['users', 'list'], ['users', 'list'])).toBe(true);
  });

  it('should match partial prefix patterns', () => {
    expect(matchesQueryKey(['users', 'list', { status: 'active' }], ['users'])).toBe(true);
    expect(matchesQueryKey(['users', 'list', { status: 'active' }], ['users', 'list'])).toBe(true);
  });

  it('should not match when pattern is longer than key', () => {
    expect(matchesQueryKey(['users'], ['users', 'list'])).toBe(false);
  });

  it('should not match different values', () => {
    expect(matchesQueryKey(['users', 'list'], ['events', 'list'])).toBe(false);
  });

  it('should support wildcard (*) matching', () => {
    expect(matchesQueryKey(['users', 'list'], ['*', 'list'])).toBe(true);
    expect(matchesQueryKey(['events', 'list'], ['*', 'list'])).toBe(true);
  });

  it('should match subset of object pattern', () => {
    expect(
      matchesQueryKey(
        ['users', 'list', { status: 'active', role: 'admin' }],
        ['users', 'list', { status: 'active' }],
      ),
    ).toBe(true);
  });

  it('should not match when object values differ', () => {
    expect(
      matchesQueryKey(
        ['users', 'list', { status: 'active' }],
        ['users', 'list', { status: 'inactive' }],
      ),
    ).toBe(false);
  });
});

// =============================================================================
// Pre-defined factories
// =============================================================================

describe('pre-defined query key factories', () => {
  it('should create userKeys', () => {
    expect(userKeys.all).toEqual(['users']);
    expect(userKeys.list()).toEqual(['users', 'list']);
    expect(userKeys.detail('u1')).toEqual(['users', 'detail', 'u1']);
  });

  it('should create eventKeys', () => {
    expect(eventKeys.all).toEqual(['events']);
  });

  it('should create sessionKeys', () => {
    expect(sessionKeys.all).toEqual(['sessions']);
  });

  it('should create tenantKeys', () => {
    expect(tenantKeys.all).toEqual(['tenants']);
  });

  it('should create projectKeys', () => {
    expect(projectKeys.all).toEqual(['projects']);
  });

  it('should create dashboardKeys', () => {
    expect(dashboardKeys.all).toEqual(['dashboards']);
  });

  it('should create reportKeys', () => {
    expect(reportKeys.all).toEqual(['reports']);
  });
});
