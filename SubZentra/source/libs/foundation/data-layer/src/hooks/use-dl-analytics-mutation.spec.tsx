import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';

import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useDLAnalyticsMutation } from './use-dl-analytics-mutation';

const createInternals = (): DataLayerInternals => {
  const queryClient = new QueryClient();
  const duckdbRouter = {
    query: vi.fn().mockResolvedValue({
      rows: [],
      executionTimeMs: 3,
      columns: [],
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
    syncCoordinator: {},
    duckdbRouter,
    opfsManager: null,
    analyticsEnabled: true,
    initializeAnalytics: vi.fn().mockResolvedValue({ duckdbRouter, opfsManager: null }),
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

describe('useDLAnalyticsMutation', () => {
  it('executes mutation SQL and invalidates provided query keys', async () => {
    const internals = createInternals();
    const invalidateSpy = vi.spyOn(internals.queryClient, 'invalidateQueries');

    const { result } = renderHook(
      () =>
        useDLAnalyticsMutation<{ id: string }>({
          sql: (variables) => `DELETE FROM events WHERE id = '${variables.id}'`,
          invalidateKeys: [['analytics', 'events']],
        }),
      { wrapper: createWrapper(internals) },
    );

    await act(async () => {
      await result.current.mutateAsync({ id: 'evt_1' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(internals.duckdbRouter?.query).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['analytics', 'events'] });
  });
});
