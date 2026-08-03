import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';

import {
  CONFLICT_RESOLUTION_TYPE,
  SYNC_EVENT_TYPE,
  type SyncEvent,
} from '@open-zentra/foundation-data-model';

import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useConflictResolution } from './use-conflict-resolution';

const createInternals = () => {
  const queryClient = new QueryClient();
  let listener: ((event: SyncEvent) => void) | null = null;
  const queueManager = {
    enqueue: vi.fn().mockResolvedValue(undefined),
  };
  const syncCoordinator = {
    subscribe: vi.fn((callback: (event: SyncEvent) => void) => {
      listener = callback;
      return () => {
        listener = null;
      };
    }),
    getQueueManager: vi.fn(() => queueManager),
    invalidateQueries: vi.fn(),
  };

  const base = {
    queryClient,
    axiosInstance: { request: vi.fn(), defaults: {} },
    realtimeClient: {
      subscribeStatus: vi.fn(() => vi.fn()),
      subscribeMessages: vi.fn(() => vi.fn()),
      connect: vi.fn(async () => undefined),
      close: vi.fn(),
      send: vi.fn(),
    },
    realtimeStatus: 'idle',
    lastRealtimeMessage: null,
    database: {
      syncState: {
        getRaw: vi.fn().mockResolvedValue([]),
        set: vi.fn().mockResolvedValue(undefined),
      },
    },
    syncCoordinator,
    duckdbRouter: null,
    opfsManager: null,
    analyticsEnabled: true,
    initializeAnalytics: vi.fn().mockResolvedValue(null),
    isOnline: true,
    cacheConfig: {
      defaultStaleTime: 60_000,
      defaultGcTime: 300_000,
      analyticsStaleTime: 60_000,
      analyticsGcTime: 300_000,
    },
    tableRegistry: {},
    datasourceEndpoint: null,
    getTableSyncService: vi.fn(),
    getFileDownloadService: vi.fn().mockResolvedValue(null),
  } satisfies Record<string, unknown>;

  return {
    internals: base as unknown as DataLayerInternals,
    queueManager,
    syncState: base.database.syncState,
    emit: (event: SyncEvent) => listener?.(event),
  };
};

const createWrapper = (internals: DataLayerInternals) => {
  const Wrapper = ({ children }: PropsWithChildren): React.ReactElement => (
    <QueryClientProvider client={internals.queryClient}>
      <DataLayerInternalsContext.Provider value={internals}>
        {children}
      </DataLayerInternalsContext.Provider>
    </QueryClientProvider>
  );
  return Wrapper;
};

describe('useConflictResolution', () => {
  it('adds conflict from sync events and resolves by queuing local update', async () => {
    const { internals, queueManager, syncState, emit } = createInternals();

    const { result } = renderHook(() => useConflictResolution(), {
      wrapper: createWrapper(internals),
    });

    await waitFor(() => expect(syncState.getRaw).toHaveBeenCalledTimes(1));

    act(() => {
      emit({
        type: SYNC_EVENT_TYPE.CONFLICT_DETECTED,
        timestamp: Date.now(),
        data: {
          conflictCount: 1,
          tableName: 'events',
          entityId: 'evt_1',
          localData: { id: 'evt_1', name: 'local' },
          remoteData: { id: 'evt_1', name: 'remote' },
        } as unknown as SyncEvent['data'],
      });
    });

    await waitFor(() => expect(result.current.conflictCount).toBe(1));

    await act(async () => {
      await result.current.resolveAll({
        type: CONFLICT_RESOLUTION_TYPE.ACCEPT_LOCAL,
      });
    });

    expect(queueManager.enqueue).toHaveBeenCalledTimes(1);
    expect(result.current.conflictCount).toBe(0);
  });
});
