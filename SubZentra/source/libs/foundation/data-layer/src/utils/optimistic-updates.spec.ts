/**
 * Tests for optimistic-updates utilities
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createOptimisticContext,
  optimisticAddToList,
  optimisticRemoveFromList,
  optimisticUpdateInList,
  optimisticUpdateItem,
  replaceProvisionalId,
  rollbackOptimisticUpdate,
} from './optimistic-updates';

describe('optimistic-updates utilities', () => {
  let mockQueryClient: {
    getQueryData: ReturnType<typeof vi.fn>;
    setQueryData: ReturnType<typeof vi.fn>;
    removeQueries: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    mockQueryClient = {
      getQueryData: vi.fn(),
      setQueryData: vi.fn(),
      removeQueries: vi.fn(),
    };
  });

  describe('createOptimisticContext', () => {
    it('should capture query key and previous data', () => {
      const previousData = [{ id: '1', name: 'User 1' }];
      mockQueryClient.getQueryData.mockReturnValue(previousData);

      const context = createOptimisticContext(mockQueryClient as never, ['users']);

      expect(context.queryKey).toEqual(['users']);
      expect(context.previousData).toBe(previousData);
      expect(mockQueryClient.getQueryData).toHaveBeenCalledWith(['users']);
    });

    it('should capture undefined when no previous data', () => {
      mockQueryClient.getQueryData.mockReturnValue(undefined);

      const context = createOptimisticContext(mockQueryClient as never, ['posts', '123']);

      expect(context.queryKey).toEqual(['posts', '123']);
      expect(context.previousData).toBeUndefined();
    });
  });

  describe('rollbackOptimisticUpdate', () => {
    it('should restore previous data', () => {
      const previousData = [{ id: '1', name: 'User 1' }];
      const context = {
        queryKey: ['users'],
        previousData,
      };

      rollbackOptimisticUpdate(mockQueryClient as never, context);

      expect(mockQueryClient.setQueryData).toHaveBeenCalledWith(['users'], previousData);
      expect(mockQueryClient.removeQueries).not.toHaveBeenCalled();
    });

    it('should remove query when no previous data', () => {
      const context = {
        queryKey: ['users', '999'],
        previousData: undefined,
      };

      rollbackOptimisticUpdate(mockQueryClient as never, context);

      expect(mockQueryClient.removeQueries).toHaveBeenCalledWith({
        queryKey: ['users', '999'],
      });
      expect(mockQueryClient.setQueryData).not.toHaveBeenCalled();
    });
  });

  describe('optimisticAddToList', () => {
    it('should add item to existing list', () => {
      const existingData = [{ id: '1', name: 'User 1' }];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      const newItem = { id: '2', name: 'User 2' };
      const context = optimisticAddToList(mockQueryClient as never, ['users'], newItem);

      expect(context.previousData).toBe(existingData);
      expect(mockQueryClient.setQueryData).toHaveBeenCalledWith(['users'], expect.any(Function));

      // Test the updater function
      const result = capturedUpdater?.(existingData);
      expect(result).toEqual([
        { id: '1', name: 'User 1' },
        { id: '2', name: 'User 2' },
      ]);
    });

    it('should create list with item when no existing data', () => {
      mockQueryClient.getQueryData.mockReturnValue(undefined);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      const newItem = { id: '1', name: 'First User' };
      optimisticAddToList(mockQueryClient as never, ['users'], newItem);

      const result = capturedUpdater?.(undefined);
      expect(result).toEqual([{ id: '1', name: 'First User' }]);
    });
  });

  describe('optimisticRemoveFromList', () => {
    it('should remove item by id', () => {
      const existingData = [
        { id: '1', name: 'User 1' },
        { id: '2', name: 'User 2' },
        { id: '3', name: 'User 3' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticRemoveFromList(mockQueryClient as never, ['users'], '2');

      const result = capturedUpdater?.(existingData);
      expect(result).toEqual([
        { id: '1', name: 'User 1' },
        { id: '3', name: 'User 3' },
      ]);
    });

    it('should remove only the matching id', () => {
      const existingData = [
        { id: 'user_1', name: 'User 1' },
        { id: 'user_2', name: 'User 2' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticRemoveFromList(mockQueryClient as never, ['users'], 'user_1');

      const result = capturedUpdater?.(existingData);
      expect(result).toEqual([{ id: 'user_2', name: 'User 2' }]);
    });

    it('should return unchanged list when no match', () => {
      const existingData = [{ id: '1', name: 'User 1' }];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticRemoveFromList(mockQueryClient as never, ['users'], 'nonexistent');

      const result = capturedUpdater?.(existingData);
      expect(result).toEqual([{ id: '1', name: 'User 1' }]);
    });

    it('should handle undefined list', () => {
      mockQueryClient.getQueryData.mockReturnValue(undefined);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticRemoveFromList(mockQueryClient as never, ['users'], '1');

      const result = capturedUpdater?.(undefined);
      expect(result).toBeUndefined();
    });
  });

  describe('optimisticUpdateInList', () => {
    it('should update item by id', () => {
      const existingData = [
        { id: '1', name: 'User 1' },
        { id: '2', name: 'User 2' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticUpdateInList(
        mockQueryClient as never,
        ['users'],
        '1',
        (user: { id: string; name: string }) => ({ ...user, name: 'Updated User 1' }),
      );

      const result = capturedUpdater?.(existingData) as { id: string; name: string }[];
      expect(result[0].name).toBe('Updated User 1');
      expect(result[1].name).toBe('User 2');
    });

    it('should update only the matching id', () => {
      const existingData = [
        { id: 'user_1', name: 'User 1' },
        { id: 'user_2', name: 'User 2' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticUpdateInList(
        mockQueryClient as never,
        ['users'],
        'user_2',
        (user: { id: string; name: string }) => ({ ...user, name: 'Updated User 2' }),
      );

      const result = capturedUpdater?.(existingData) as { name: string }[];
      expect(result[0].name).toBe('User 1');
      expect(result[1].name).toBe('Updated User 2');
    });

    it('should handle undefined list', () => {
      mockQueryClient.getQueryData.mockReturnValue(undefined);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticUpdateInList(
        mockQueryClient as never,
        ['users'],
        '1',
        (user: { id: string; name: string }) => user,
      );

      const result = capturedUpdater?.(undefined);
      expect(result).toBeUndefined();
    });
  });

  describe('optimisticUpdateItem', () => {
    it('should update single item', () => {
      const existingData = { id: '1', name: 'User 1', email: 'user1@test.com' };
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticUpdateItem(
        mockQueryClient as never,
        ['users', '1'],
        (user: typeof existingData | undefined) =>
          user ? { ...user, name: 'Updated Name' } : { id: '1', name: 'Updated Name', email: '' },
      );

      const result = capturedUpdater?.(existingData) as typeof existingData;
      expect(result.name).toBe('Updated Name');
      expect(result.email).toBe('user1@test.com');
    });

    it('should handle undefined item', () => {
      mockQueryClient.getQueryData.mockReturnValue(undefined);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      optimisticUpdateItem(
        mockQueryClient as never,
        ['users', '1'],
        (user: { id: string; name: string } | undefined) => user ?? { id: '1', name: 'New User' },
      );

      const result = capturedUpdater?.(undefined);
      expect(result).toEqual({ id: '1', name: 'New User' });
    });

    it('should return context for rollback', () => {
      const existingData = { id: '1', name: 'User 1' };
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      const context = optimisticUpdateItem(
        mockQueryClient as never,
        ['users', '1'],
        (user: { id: string; name: string } | undefined) => user ?? { id: '1', name: 'User 1' },
      );

      expect(context.queryKey).toEqual(['users', '1']);
      expect(context.previousData).toBe(existingData);
    });
  });

  describe('replaceProvisionalId', () => {
    it('should replace provisional id with server id', () => {
      const existingData = [
        { id: 'prov_123', name: 'New User' },
        { id: '2', name: 'User 2' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      replaceProvisionalId(mockQueryClient as never, ['users'], 'prov_123', 'server_456');

      const result = capturedUpdater?.(existingData) as {
        id: string;
        name: string;
      }[];
      expect(result[0].id).toBe('server_456');
      expect(result[0].name).toBe('New User');
      expect(result[1].id).toBe('2');
    });

    it('should replace repeated provisional ids consistently', () => {
      const existingData = [
        { id: 'prov_123', name: 'New User' },
        { id: 'prov_123', name: 'Draft Copy' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      replaceProvisionalId(mockQueryClient as never, ['users'], 'prov_123', 'server_789');

      const result = capturedUpdater?.(existingData) as { id: string; name: string }[];
      expect(result[0].id).toBe('server_789');
      expect(result[1].id).toBe('server_789');
    });

    it('should not modify non-matching items', () => {
      const existingData = [
        { id: '1', name: 'User 1' },
        { id: '2', name: 'User 2' },
      ];
      mockQueryClient.getQueryData.mockReturnValue(existingData);

      let capturedUpdater: ((old: unknown[]) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      replaceProvisionalId(mockQueryClient as never, ['users'], 'nonexistent', 'server_999');

      const result = capturedUpdater?.(existingData);
      expect(result).toEqual(existingData);
    });

    it('should handle undefined list', () => {
      mockQueryClient.getQueryData.mockReturnValue(undefined);

      let capturedUpdater: ((old: unknown) => unknown) | undefined;
      mockQueryClient.setQueryData.mockImplementation((key, updater) => {
        capturedUpdater = updater;
      });

      replaceProvisionalId(mockQueryClient as never, ['users'], 'prov_123', 'server_456');

      const result = capturedUpdater?.(undefined);
      expect(result).toBeUndefined();
    });
  });
});
