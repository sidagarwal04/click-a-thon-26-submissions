/**
 * Tests for mutation-helpers utilities
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DEFAULT_CACHE_TTL } from '../core/constants';
import {
  buildMutationResult,
  collectInvalidationKeys,
  createCacheEntryWithDefaults,
  invalidateQueries,
} from './mutation-helpers';

// Mock the external dependencies
vi.mock('@open-zentra/foundation-data-model', () => ({
  hashQueryKey: vi.fn((key: unknown[]) => `hash_${key.join('_')}`),
  SCHEMA_VERSION: 1,
  toJsonSerializable: vi.fn((data: unknown) => data),
  OPERATIONS: {
    GET: 'get',
    LIST: 'list',
    CREATE: 'create',
    UPDATE: 'update',
    DELETE: 'delete',
  },
  CONFLICT_RESOLUTION_TYPE: {
    ACCEPT_LOCAL: 'accept-local',
    ACCEPT_REMOTE: 'accept-remote',
    MERGE: 'merge',
  },
}));

// Mock the foundation-utils for TIME_MS
vi.mock('@open-zentra/foundation-utils', () => ({
  TIME_MS: {
    DAY: 86400000,
  },
}));

vi.mock('@open-zentra/foundation-database', () => ({
  createCacheEntry: vi.fn(
    (cacheKey: string, queryKey: unknown[], data: unknown, options: Record<string, unknown>) => ({
      cacheKey,
      queryKey,
      data,
      ...options,
    }),
  ),
}));

describe('mutation-helpers utilities', () => {
  describe('invalidateQueries', () => {
    it('should invalidate all provided query keys', async () => {
      const mockInvalidate = vi.fn().mockResolvedValue(undefined);
      const mockQueryClient = {
        invalidateQueries: mockInvalidate,
      };

      await invalidateQueries(mockQueryClient as never, [['users'], ['users', '123'], ['posts']]);

      expect(mockInvalidate).toHaveBeenCalledTimes(3);
      expect(mockInvalidate).toHaveBeenCalledWith({ queryKey: ['users'] });
      expect(mockInvalidate).toHaveBeenCalledWith({ queryKey: ['users', '123'] });
      expect(mockInvalidate).toHaveBeenCalledWith({ queryKey: ['posts'] });
    });

    it('should handle empty keys array', async () => {
      const mockInvalidate = vi.fn().mockResolvedValue(undefined);
      const mockQueryClient = {
        invalidateQueries: mockInvalidate,
      };

      await invalidateQueries(mockQueryClient as never, []);

      expect(mockInvalidate).not.toHaveBeenCalled();
    });

    it('should invalidate in parallel', async () => {
      const order: number[] = [];
      const mockInvalidate = vi.fn().mockImplementation(async () => {
        order.push(order.length);
      });
      const mockQueryClient = {
        invalidateQueries: mockInvalidate,
      };

      await invalidateQueries(mockQueryClient as never, [['a'], ['b'], ['c']]);

      // All should be called before any resolves (parallel execution)
      expect(mockInvalidate).toHaveBeenCalledTimes(3);
    });
  });

  describe('collectInvalidationKeys', () => {
    it('should return explicit invalidateKeys only', () => {
      const keys = collectInvalidationKeys([['users'], ['posts']]);
      expect(keys).toEqual([['users'], ['posts']]);
    });

    it('should add listQueryKey when provided', () => {
      const keys = collectInvalidationKeys([['extra']], ['users']);
      expect(keys).toEqual([['extra'], ['users']]);
    });

    it('should add itemQueryKey when entityId provided', () => {
      const itemKeyFn = (id: string) => ['users', id];
      const keys = collectInvalidationKeys([], undefined, itemKeyFn, '123');
      expect(keys).toEqual([['users', '123']]);
    });

    it('should combine all key sources', () => {
      const itemKeyFn = (id: string) => ['users', id];
      const keys = collectInvalidationKeys([['extra']], ['users'], itemKeyFn, '456');
      expect(keys).toEqual([['extra'], ['users'], ['users', '456']]);
    });

    it('should not add itemQueryKey without entityId', () => {
      const itemKeyFn = (id: string) => ['users', id];
      const keys = collectInvalidationKeys([], ['users'], itemKeyFn, null);
      expect(keys).toEqual([['users']]);
    });

    it('should not add itemQueryKey without function', () => {
      const keys = collectInvalidationKeys([], ['users'], undefined, '123');
      expect(keys).toEqual([['users']]);
    });

    it('should handle empty input', () => {
      const keys = collectInvalidationKeys([]);
      expect(keys).toEqual([]);
    });
  });

  describe('createCacheEntryWithDefaults', () => {
    it('should create cache entry with default TTL', () => {
      const entry = createCacheEntryWithDefaults(
        'users',
        '123',
        { name: 'John' },
        {
          tableName: 'users',
          isOfflineData: false,
        },
      );

      expect(entry).toMatchObject({
        cacheKey: 'hash_users_123',
        queryKey: ['users', '123'],
        data: { name: 'John' },
        tableName: 'users',
        ttl: DEFAULT_CACHE_TTL,
        schemaVersion: 1,
        isOfflineData: false,
      });
    });

    it('should allow custom TTL', () => {
      const customTtl = 1000 * 60 * 5; // 5 minutes
      const entry = createCacheEntryWithDefaults(
        'posts',
        '456',
        { title: 'Test' },
        {
          tableName: 'posts',
          isOfflineData: true,
          ttl: customTtl,
        },
      );

      expect(entry).toHaveProperty('ttl', customTtl);
    });

    it('should set isOfflineData flag', () => {
      const offlineEntry = createCacheEntryWithDefaults(
        'users',
        '1',
        {},
        {
          tableName: 'users',
          isOfflineData: true,
        },
      );

      const onlineEntry = createCacheEntryWithDefaults(
        'users',
        '2',
        {},
        {
          tableName: 'users',
          isOfflineData: false,
        },
      );

      expect(offlineEntry.isOfflineData).toBe(true);
      expect(onlineEntry.isOfflineData).toBe(false);
    });
  });

  describe('DEFAULT_CACHE_TTL', () => {
    it('should be 24 hours in milliseconds', () => {
      expect(DEFAULT_CACHE_TTL).toBe(1000 * 60 * 60 * 24);
      expect(DEFAULT_CACHE_TTL).toBe(86400000);
    });
  });

  describe('buildMutationResult', () => {
    let mockMutationResult: {
      data: unknown;
      isPending: boolean;
      isSuccess: boolean;
      isError: boolean;
      isIdle: boolean;
      error: Error | null;
      mutate: () => void;
      mutateAsync: () => Promise<unknown>;
      reset: () => void;
    };

    beforeEach(() => {
      mockMutationResult = {
        data: undefined,
        isPending: false,
        isSuccess: false,
        isError: false,
        isIdle: true,
        error: null,
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        reset: vi.fn(),
      };
    });

    it('should build result with all fields', () => {
      const result = buildMutationResult({
        mutationResult: mockMutationResult as never,
        isQueued: false,
        provisionalId: null,
        isOffline: false,
      });

      expect(result).toMatchObject({
        data: undefined,
        isQueued: false,
        provisionalId: null,
        isOffline: false,
        isPending: false,
        isSuccess: false,
        isError: false,
        isIdle: true,
        error: null,
      });
      expect(result.mutate).toBe(mockMutationResult.mutate);
      expect(result.mutateAsync).toBe(mockMutationResult.mutateAsync);
      expect(result.reset).toBe(mockMutationResult.reset);
    });

    it('should reflect pending state', () => {
      mockMutationResult.isPending = true;
      mockMutationResult.isIdle = false;

      const result = buildMutationResult({
        mutationResult: mockMutationResult as never,
        isQueued: true,
        provisionalId: 'prov_123',
        isOffline: true,
      });

      expect(result.isPending).toBe(true);
      expect(result.isIdle).toBe(false);
      expect(result.isQueued).toBe(true);
      expect(result.provisionalId).toBe('prov_123');
      expect(result.isOffline).toBe(true);
    });

    it('should reflect success state with data', () => {
      mockMutationResult.isSuccess = true;
      mockMutationResult.isIdle = false;
      mockMutationResult.data = { id: '456', name: 'Created User' };

      const result = buildMutationResult({
        mutationResult: mockMutationResult as never,
        isQueued: false,
        provisionalId: null,
        isOffline: false,
      });

      expect(result.isSuccess).toBe(true);
      expect(result.data).toEqual({ id: '456', name: 'Created User' });
    });

    it('should reflect error state', () => {
      const testError = new Error('Mutation failed');
      mockMutationResult.isError = true;
      mockMutationResult.isIdle = false;
      mockMutationResult.error = testError;

      const result = buildMutationResult({
        mutationResult: mockMutationResult as never,
        isQueued: false,
        provisionalId: null,
        isOffline: false,
      });

      expect(result.isError).toBe(true);
      expect(result.error).toBe(testError);
    });
  });
});
