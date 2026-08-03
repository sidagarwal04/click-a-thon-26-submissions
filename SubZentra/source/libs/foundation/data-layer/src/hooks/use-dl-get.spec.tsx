import React, { type PropsWithChildren } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';

import { DATA_SOURCE, type ApiQueryDescriptor } from '@open-zentra/foundation-data-model';

import type { DataLayerInternals } from '../provider/data-layer-internals-context';
import { DataLayerInternalsContext } from '../provider/data-layer-internals-context';
import { useDLGet } from './use-dl-get';

const createInternals = (overrides: Partial<DataLayerInternals> = {}): DataLayerInternals => {
  const queryClient = overrides.queryClient ?? new QueryClient();
  const axiosInstance =
    overrides.axiosInstance ??
    ({
      request: vi.fn(),
      defaults: {},
    } as unknown as DataLayerInternals['axiosInstance']);
  const defaultInternals = {
    queryClient,
    axiosInstance,
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
        get: vi.fn().mockResolvedValue(undefined),
        set: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
    },
    syncCoordinator: {
      getQueueManager: vi.fn(),
    },
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
    ...(defaultInternals as unknown as DataLayerInternals),
    ...overrides,
    queryClient,
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

describe('useDLGet', () => {
  it('loads data from the API when online', async () => {
    const apiResult = { id: 'evt_1', type: 'click' };
    const request = vi.fn().mockResolvedValue({ data: apiResult });
    const internals = createInternals({
      isOnline: true,
      axiosInstance: {
        request,
        defaults: {},
      } as unknown as DataLayerInternals['axiosInstance'],
    });

    // Left at the default type parameters. ApiQueryDescriptor is contravariant
    // in TArgs (it appears in `path`'s parameter position), so a descriptor
    // narrowed to { id: string } does not satisfy the hook's own
    // `TQuery extends ApiQueryDescriptor` constraint. The assertions below are
    // structural, so nothing here needs the narrower type.
    const queryRef: ApiQueryDescriptor = { path: '/events/evt_1' };
    const { result } = renderHook(
      () => useDLGet({ query: queryRef, table: 'events', args: { id: 'evt_1' } }),
      { wrapper: createWrapper(internals) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(request).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(apiResult);
    expect(result.current.dataSource).toBe(DATA_SOURCE.API);
  });

  it('falls back to cache when offline', async () => {
    const cachedResult = { id: 'evt_cached', type: 'view' };
    const queries = {
      get: vi.fn().mockResolvedValue({ data: cachedResult }),
      set: vi.fn().mockResolvedValue(undefined),
      delete: vi.fn().mockResolvedValue(undefined),
    };
    const internals = createInternals({
      isOnline: false,
      database: { queries } as unknown as DataLayerInternals['database'],
    });

    const queryRef: ApiQueryDescriptor = { path: '/events/evt_cached' };
    const { result } = renderHook(
      () => useDLGet({ query: queryRef, table: 'events', args: { id: 'evt_cached' } }),
      { wrapper: createWrapper(internals) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queries.get).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(cachedResult);
    expect(result.current.dataSource).toBe(DATA_SOURCE.CACHE);
  });
});
