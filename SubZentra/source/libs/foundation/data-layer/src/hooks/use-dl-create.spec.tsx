import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';

import type { ApiMutationDescriptor } from '@open-zentra/foundation-data-model';
import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useDLCreate } from './use-dl-create';

const createInternals = (): DataLayerInternals => {
  const queryClient = new QueryClient();
  const queueManager = {
    enqueue: vi.fn().mockResolvedValue(undefined),
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
        delete: vi.fn().mockResolvedValue(undefined),
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

describe('useDLCreate', () => {
  it('queues create mutation and returns optimistic data when offline', async () => {
    const internals = createInternals();
    const queueManager = internals.syncCoordinator.getQueueManager();

    internals.queryClient.setQueryData(['events'], []);

    const { result } = renderHook(
      () =>
        useDLCreate({
          // Default type parameters: ApiMutationDescriptor is contravariant in
          // TArgs, so a narrowed descriptor does not satisfy the hook's
          // `TMutation extends ApiMutationDescriptor` constraint.
          mutation: {
            method: 'POST',
            path: '/events',
          } as ApiMutationDescriptor,
          table: 'events',
          listQueryKey: ['events'],
          onOptimistic: (variables) => ({ name: (variables as { name: string }).name }),
        }),
      { wrapper: createWrapper(internals) },
    );

    let response: { id?: string; name?: string } | undefined;
    await act(async () => {
      response = (await result.current.mutateAsync({ name: 'offline-event' })) as {
        id?: string;
        name?: string;
      };
    });

    await waitFor(() => expect(queueManager.enqueue).toHaveBeenCalledTimes(1));
    expect(response?.name).toBe('offline-event');
    expect(response?.id).toBeDefined();
    expect(result.current.isQueued).toBe(true);
  });
});
