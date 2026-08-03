import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';

import type { ApiMutationDescriptor } from '@open-zentra/foundation-data-model';
import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useDLUpdate } from './use-dl-update';

const createInternals = (): DataLayerInternals => {
  const queryClient = new QueryClient();
  const queueManager = {
    enqueue: vi.fn().mockResolvedValue(undefined),
    resolveId: vi.fn((id: string) => id),
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
      queries: {
        set: vi.fn().mockResolvedValue(undefined),
      },
    },
    syncCoordinator: {
      getQueueManager: vi.fn(() => queueManager),
    },
    duckdbRouter: null,
    opfsManager: null,
    analyticsEnabled: true,
    initializeAnalytics: vi.fn().mockResolvedValue(null),
    isOnline: false,
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

  return base as unknown as DataLayerInternals;
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

describe('useDLUpdate', () => {
  it('queues update mutation and returns optimistic data when offline', async () => {
    const internals = createInternals();
    const queueManager = internals.syncCoordinator.getQueueManager();

    internals.queryClient.setQueryData(['events', 'evt_1'], { id: 'evt_1', name: 'old-name' });

    const { result } = renderHook(
      () =>
        useDLUpdate({
          // Default type parameters: ApiMutationDescriptor is contravariant in
          // TArgs, so a narrowed descriptor does not satisfy the hook's
          // `TMutation extends ApiMutationDescriptor` constraint.
          mutation: {
            method: 'PATCH',
            path: (args) => `/events/${(args as { id: string }).id}`,
            body: (args) => {
              const { id: _entityId, ...payload } = args as { id: string; name?: string };
              return payload;
            },
          } as ApiMutationDescriptor,
          table: 'events',
          listQueryKey: ['events'],
          itemQueryKey: (id) => ['events', id],
          getEntityId: (variables) => (variables as { id: string }).id,
          onOptimistic: (variables, previous) => ({
            ...((previous as object | undefined) ?? {}),
            id: (variables as { id: string }).id,
            name: 'new-name',
          }),
        }),
      { wrapper: createWrapper(internals) },
    );

    let response: unknown;
    await act(async () => {
      response = await result.current.mutateAsync({ id: 'evt_1' });
    });

    await waitFor(() => expect(queueManager.enqueue).toHaveBeenCalledTimes(1));
    expect(response).toEqual({ id: 'evt_1', name: 'new-name' });
    expect(result.current.isQueued).toBe(true);
  });
});
