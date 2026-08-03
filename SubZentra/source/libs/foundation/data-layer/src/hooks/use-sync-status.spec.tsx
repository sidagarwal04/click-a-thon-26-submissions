import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';

import { SYNC_EVENT_TYPE, type SyncEvent } from '@open-zentra/foundation-data-model';

import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useSyncStatus } from './use-sync-status';

const createInternals = () => {
  const queryClient = new QueryClient();
  let listener: ((event: SyncEvent) => void) | null = null;

  const syncCoordinator = {
    getState: vi.fn().mockResolvedValue({
      isOnline: true,
      isSyncing: false,
      pendingMutations: 2,
      failedMutations: 1,
      lastSyncAt: 1234,
      isLeader: true,
    }),
    subscribe: vi.fn((callback: (event: SyncEvent) => void) => {
      listener = callback;
      return () => {
        listener = null;
      };
    }),
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
    database: {},
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

describe('useSyncStatus', () => {
  it('loads initial sync state and reacts to sync events', async () => {
    const { internals, emit } = createInternals();
    const { result } = renderHook(() => useSyncStatus(), {
      wrapper: createWrapper(internals),
    });

    await waitFor(() => expect(result.current.pendingCount).toBe(2));
    expect(result.current.failedCount).toBe(1);
    expect(result.current.lastSyncedAt).toBe(1234);
    expect(result.current.isLeader).toBe(true);

    act(() => {
      emit({
        type: SYNC_EVENT_TYPE.SYNC_START,
        timestamp: Date.now(),
      });
    });
    expect(result.current.isSyncing).toBe(true);

    act(() => {
      emit({
        type: SYNC_EVENT_TYPE.SYNC_COMPLETE,
        timestamp: 9999,
      });
    });
    expect(result.current.isSyncing).toBe(false);
    expect(result.current.lastSyncedAt).toBe(9999);
  });
});
