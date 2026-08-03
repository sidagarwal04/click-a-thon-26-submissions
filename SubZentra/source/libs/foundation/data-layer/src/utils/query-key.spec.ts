/**
 * Tests for query-key utilities
 */

import { describe, expect, it } from 'vitest';

import { buildQueryKey, getDataSource } from './query-key';

describe('query-key utilities', () => {
  describe('buildQueryKey', () => {
    it('should build key with just table name', () => {
      const key = buildQueryKey('users');
      expect(key).toEqual(['users']);
    });

    it('should build key with table and entityId', () => {
      const key = buildQueryKey('users', '123');
      expect(key).toEqual(['users', '123']);
    });

    it('should build key with table and args (no entityId)', () => {
      const key = buildQueryKey('users', undefined, { limit: 10 });
      expect(key).toEqual(['users', { limit: 10 }]);
    });

    it('should build key with table, entityId, and args', () => {
      const key = buildQueryKey('users', '123', { include: 'posts' });
      expect(key).toEqual(['users', '123', { include: 'posts' }]);
    });

    it('should not include undefined entityId in key', () => {
      const key = buildQueryKey('posts', undefined, { status: 'published' });
      expect(key).toEqual(['posts', { status: 'published' }]);
      expect(key.length).toBe(2);
    });

    it('should not include undefined args in key', () => {
      const key = buildQueryKey('posts', '456', undefined);
      expect(key).toEqual(['posts', '456']);
      expect(key.length).toBe(2);
    });

    it('should handle empty string entityId', () => {
      // Empty string is falsy, so it should not be included
      const key = buildQueryKey('users', '', { filter: 'active' });
      expect(key).toEqual(['users', { filter: 'active' }]);
    });

    it('should handle complex args objects', () => {
      const args = {
        filters: { status: 'active', role: 'admin' },
        pagination: { page: 1, limit: 20 },
        sort: [{ field: 'createdAt', order: 'desc' }],
      };
      const key = buildQueryKey('users', undefined, args);
      expect(key).toEqual(['users', args]);
    });

    it('should handle null args', () => {
      // null is falsy, so it should NOT be included
      const key = buildQueryKey('users', '123', null);
      expect(key).toEqual(['users', '123']);
    });
  });

  describe('getDataSource', () => {
    it('should return "none" when no data', () => {
      expect(getDataSource(false, true, false)).toBe('none');
      expect(getDataSource(false, false, false)).toBe('none');
      expect(getDataSource(false, true, true)).toBe('none');
    });

    it('should return "cache" when offline with data', () => {
      expect(getDataSource(true, false, false)).toBe('cache');
      expect(getDataSource(true, false, true)).toBe('cache');
    });

    it('should return "cache" when fetching', () => {
      expect(getDataSource(true, true, true)).toBe('cache');
    });

    it('should return "api" when online, has data, not fetching', () => {
      expect(getDataSource(true, true, false)).toBe('api');
    });

    it('should prioritize hasData check', () => {
      // No data always returns 'none', regardless of other states
      expect(getDataSource(false, false, true)).toBe('none');
      expect(getDataSource(false, true, true)).toBe('none');
    });

    it('should prioritize offline over fetching', () => {
      // Offline with data returns 'cache'
      expect(getDataSource(true, false, true)).toBe('cache');
      expect(getDataSource(true, false, false)).toBe('cache');
    });
  });
});
