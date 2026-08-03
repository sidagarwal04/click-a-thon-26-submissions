import { describe, expect, it, vi } from 'vitest';

import '@open-zentra/foundation-database';

import {
  generateProvisionalId,
  MUTATION_STATUS,
  MUTATION_TYPE,
  type MutationQueueEntry,
} from '@open-zentra/foundation-data-model';

import type { ConflictResolver } from '../conflicts/resolver';
import type { OfflineQueueManager } from './manager';
import { QueueProcessor, type MutationExecutorResult } from './processor';

const createMutation = (overrides: Partial<MutationQueueEntry> = {}): MutationQueueEntry => ({
  id: 'mutation-1',
  idempotencyKey: 'mutation-1',
  timestamp: Date.now(),
  status: MUTATION_STATUS.PENDING,
  type: MUTATION_TYPE.UPDATE,
  tableName: 'tasks',
  entityId: 'task-1',
  payload: { title: 'updated' },
  retryCount: 0,
  ...overrides,
});

describe('QueueProcessor', () => {
  it('fails deadlocked cyclic pending mutations instead of looping forever', async () => {
    const cyclicMutations: MutationQueueEntry[] = [
      createMutation({ id: 'a', idempotencyKey: 'a', dependsOn: ['b'] }),
      createMutation({ id: 'b', idempotencyKey: 'b', dependsOn: ['a'] }),
    ];

    const queueManager = {
      ensureInitialized: vi.fn(async () => undefined),
      getPendingMutations: vi.fn(async () => cyclicMutations),
      updateStatus: vi.fn(async () => undefined),
      deleteCompleted: vi.fn(async () => 0),
      markFailed: vi.fn(async () => undefined),
    } as unknown as OfflineQueueManager;

    const resolver = {} as ConflictResolver;
    const executor = vi.fn(async (): Promise<MutationExecutorResult> => ({ success: true }));

    const processor = new QueueProcessor({
      queueManager,
      conflictResolver: resolver,
      executor,
      autoCleanup: false,
    });

    const result = await processor.process();

    expect(result.processed).toBe(2);
    expect(result.failed).toBe(2);
    expect(result.skipped).toBe(2);
    expect(executor).not.toHaveBeenCalled();
    expect(queueManager.updateStatus).toHaveBeenCalledTimes(2);
    expect(queueManager.updateStatus).toHaveBeenNthCalledWith(
      1,
      'a',
      MUTATION_STATUS.FAILED,
      expect.objectContaining({
        lastError: expect.stringContaining('Cyclic mutation dependencies detected'),
      }),
    );
  });

  it('initializes ID mappings before processing and awaits mapping persistence', async () => {
    const provisionalId = generateProvisionalId();
    const mutation = createMutation({
      id: 'create-1',
      idempotencyKey: 'create-1',
      type: MUTATION_TYPE.CREATE,
      entityId: provisionalId,
      payload: { name: 'task' },
    });

    let pendingCalls = 0;
    const callOrder: string[] = [];

    const queueManager = {
      ensureInitialized: vi.fn(async () => {
        callOrder.push('initialized');
      }),
      getPendingMutations: vi.fn(async () => {
        pendingCalls += 1;
        return pendingCalls === 1 ? [mutation] : [];
      }),
      markInProgress: vi.fn(async () => {
        callOrder.push('in-progress');
      }),
      resolvePayloadIds: vi.fn((payload: Record<string, unknown>) => payload),
      resolveId: vi.fn((id: string) => id),
      registerIdMapping: vi.fn(async () => {
        callOrder.push('mapping-start');
        await Promise.resolve();
        callOrder.push('mapping-end');
      }),
      markCompleted: vi.fn(async () => {
        callOrder.push('completed');
      }),
      markFailed: vi.fn(async () => undefined),
      deleteCompleted: vi.fn(async () => 0),
      updateStatus: vi.fn(async () => undefined),
    } as unknown as OfflineQueueManager;

    const resolver = {
      hasConflict: vi.fn(() => false),
      resolve: vi.fn(),
    } as unknown as ConflictResolver;

    const processor = new QueueProcessor({
      queueManager,
      conflictResolver: resolver,
      executor: vi.fn(async () => ({
        success: true,
        serverId: 'server-1',
      })),
      autoCleanup: false,
    });

    const result = await processor.process();

    expect(result.succeeded).toBe(1);
    expect(result.idMappings).toHaveLength(1);
    expect(queueManager.ensureInitialized).toHaveBeenCalledTimes(1);
    expect(callOrder.indexOf('initialized')).toBeLessThan(callOrder.indexOf('in-progress'));
    expect(callOrder.indexOf('mapping-end')).toBeLessThan(callOrder.indexOf('completed'));
  });

  it('surfaces ID mapping persistence failures deterministically', async () => {
    const provisionalId = generateProvisionalId();
    const mutation = createMutation({
      id: 'create-fail-1',
      idempotencyKey: 'create-fail-1',
      type: MUTATION_TYPE.CREATE,
      entityId: provisionalId,
      payload: { name: 'task' },
    });

    let pendingCalls = 0;
    const queueManager = {
      ensureInitialized: vi.fn(async () => undefined),
      getPendingMutations: vi.fn(async () => {
        pendingCalls += 1;
        return pendingCalls === 1 ? [mutation] : [];
      }),
      markInProgress: vi.fn(async () => undefined),
      resolvePayloadIds: vi.fn((payload: Record<string, unknown>) => payload),
      resolveId: vi.fn((id: string) => id),
      registerIdMapping: vi.fn(async () => {
        throw new Error('persist failed');
      }),
      markCompleted: vi.fn(async () => undefined),
      markFailed: vi.fn(async () => undefined),
      deleteCompleted: vi.fn(async () => 0),
      updateStatus: vi.fn(async () => undefined),
    } as unknown as OfflineQueueManager;

    const resolver = {
      hasConflict: vi.fn(() => false),
      resolve: vi.fn(),
    } as unknown as ConflictResolver;

    const onError = vi.fn();

    const processor = new QueueProcessor({
      queueManager,
      conflictResolver: resolver,
      executor: vi.fn(async () => ({
        success: true,
        serverId: 'server-1',
      })),
      retryConfig: { maxAttempts: 1 },
      onError,
      autoCleanup: false,
    });

    const result = await processor.process();

    expect(result.processed).toBe(1);
    expect(result.failed).toBe(1);
    expect(result.succeeded).toBe(0);
    expect(queueManager.registerIdMapping).toHaveBeenCalledTimes(1);
    expect(queueManager.markFailed).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledTimes(1);
  });
});
