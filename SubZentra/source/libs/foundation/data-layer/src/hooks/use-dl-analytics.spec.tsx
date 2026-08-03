import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';

import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useDLAnalytics } from './use-dl-analytics';

const createInternals = (): DataLayerInternals => {
  const queryClient = new QueryClient();
  const duckdbRouter = {
    query: vi.fn().mockResolvedValue({
      rows: [{ count: 2 }],
      executionTimeMs: 12,
      columns: [{ name: 'count', type: 'INTEGER' }],
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

describe('useDLAnalytics', () => {
  it('executes analytics SQL and exposes rows/execution time', async () => {
    const internals = createInternals();
    const { result } = renderHook(
      () => useDLAnalytics({ sql: 'SELECT 1 as count', queryKey: ['analytics', 'count'] }),
      { wrapper: createWrapper(internals) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(internals.duckdbRouter?.query).toHaveBeenCalledTimes(1);
    expect(result.current.rows).toEqual([{ count: 2 }]);
    expect(result.current.executionTimeMs).toBe(12);
    expect(result.current.isAvailable).toBe(true);
  });
});
