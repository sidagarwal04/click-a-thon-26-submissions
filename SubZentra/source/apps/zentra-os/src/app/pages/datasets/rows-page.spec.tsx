/// <reference types="vitest/globals" />
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import type { IdentityContext } from '../../types';

import { RowsPage } from './rows-page';

const getToken = async () => 'test-token';

const identity: IdentityContext = {
  user_id: '10000000-0000-0000-0000-000000000001',
  tenant_id: '20000000-0000-0000-0000-000000000002',
  email: 'owner@example.com',
  tenant_name: 'Acme Europe',
  role: 'owner',
};

const SOURCE = {
  data_source_id: '40000000-0000-0000-0000-000000000004',
  name: 'click-house-db',
  kind: 'connected',
  health: 'reachable',
};

const ROWS_PAGE_1 = {
  data_source_id: SOURCE.data_source_id,
  table_name: 'orders',
  columns: ['id', 'status'],
  rows: [
    ['1', 'paid'],
    ['2', 'pending'],
  ],
  total: 4213,
  page: 1,
  page_size: 50,
};

const ROWS_PAGE_2 = {
  ...ROWS_PAGE_1,
  rows: [['51', 'paid']],
  page: 2,
};

/** Answer each endpoint by URL, so ordering between them cannot matter. */
const route = (handlers: Record<string, { status?: number; body: unknown }>) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    const key = Object.keys(handlers).find((fragment) => url.includes(fragment));
    const handler = key ? handlers[key] : undefined;
    if (!handler) throw new Error(`unhandled request: ${url}`);
    return {
      ok: (handler.status ?? 200) < 400,
      status: handler.status ?? 200,
      json: async () => handler.body,
    } as Response;
  });

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter
      initialEntries={[`/datasets/${SOURCE.data_source_id}/tables/orders/rows`]}
    >
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route
            path="/datasets/:dataSourceId/tables/:tableName/rows"
            element={<RowsPage getToken={getToken} identity={identity} />}
          />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('RowsPage', () => {
  it('shows neither rows nor an error before the response resolves', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise<Response>(() => undefined),
    );

    renderPage();

    expect(screen.queryByRole('table')).toBeFalsy();
    expect(screen.queryByText(/still syncing/i)).toBeFalsy();
    expect(screen.queryByText('Rows could not be read')).toBeFalsy();
  });

  it('renders the fully-qualified title, the table and the pager', async () => {
    route({
      '/rows': { body: ROWS_PAGE_1 },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();

    expect(await screen.findByText('click-house-db.orders')).toBeTruthy();
    expect(screen.getByText('paid')).toBeTruthy();
    expect(screen.getByText('pending')).toBeTruthy();
    expect(screen.getByText(/Rows 1-50 of 4,213/)).toBeTruthy();
  });

  it('shows a still-syncing message on a 404, not a generic error', async () => {
    route({
      '/rows': { status: 404, body: { detail: 'Not Found' } },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();

    expect(await screen.findByText(/still syncing/i)).toBeTruthy();
  });

  it('shows the same still-syncing message on a 503', async () => {
    route({
      '/rows': { status: 503, body: { detail: 'Cube unreachable' } },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();

    expect(await screen.findByText(/still syncing/i)).toBeTruthy();
  });

  it('shows a generic error for anything else, distinct from not-ready copy', async () => {
    route({
      '/rows': { status: 500, body: { detail: 'boom' } },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();

    expect(await screen.findByText('Rows could not be read')).toBeTruthy();
    expect(screen.queryByText(/still syncing/i)).toBeFalsy();
  });

  it('pages forward and back, updating the URL and the query', async () => {
    const fetchMock = route({
      'page=2': { body: ROWS_PAGE_2 },
      '/rows': { body: ROWS_PAGE_1 },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    await screen.findByText('paid');

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes('page=2')),
      ).toBe(true);
    });
    expect(await screen.findByText('51')).toBeTruthy();

    const prevButton = screen.getByRole('button', { name: /prev/i });
    expect(prevButton).not.toBeDisabled();
  });
});
