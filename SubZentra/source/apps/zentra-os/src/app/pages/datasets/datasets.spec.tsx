/// <reference types="vitest/globals" />
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import type { IdentityContext } from '../../types';

import { DatasetsPage } from './datasets-page';

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
  connection_hint: 'ixirbbg74s.ap-south-1.aws.clickhouse.cloud/clickathon',
};

const CATALOG = {
  catalog_version_id: '50000000-0000-0000-0000-000000000005',
  data_source_id: SOURCE.data_source_id,
  harvest_run_id: '60000000-0000-0000-0000-000000000006',
  created_at: '2026-08-01T20:51:00Z',
  tables: [
    {
      table_id: '70000000-0000-0000-0000-000000000007',
      name: 'purchase_completed',
      database: 'clickathon',
      engine: 'MergeTree',
      estimated_rows: 7054,
      size_bytes: 883029,
      agent_visible: true,
      fields: [
        {
          field_id: '80000000-0000-0000-0000-000000000008',
          name: 'user_id',
          declared_type: 'String',
          family: 'string',
          nullable: false,
          position: 0,
          profile: { sampled_rows: 1000, null_fraction: 0, distinct_count: 990 },
          agent_visible: true,
        },
        {
          field_id: '80000000-0000-0000-0000-000000000009',
          name: 'coupon_name',
          declared_type: 'Nullable(String)',
          family: 'string',
          nullable: true,
          position: 1,
          agent_visible: true,
        },
      ],
    },
  ],
  unreadable: [],
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
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route
            path="/"
            element={<DatasetsPage getToken={getToken} identity={identity} />}
          />
          <Route
            path="/datasets/:dataSourceId/tables/:tableName/rows"
            element={<p>rows page reached</p>}
          />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('Datasets', () => {
  it('points at Connections when nothing is connected', async () => {
    route({ '/v1/connector/sources': { body: [] } });

    renderPage();

    expect(await screen.findByText(/No datasets yet/i)).toBeTruthy();
  });

  it('lists the tables a harvest found, with their shape', async () => {
    route({
      '/catalog': { body: CATALOG },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();

    expect(await screen.findByText('purchase_completed')).toBeTruthy();
    expect(screen.getByText(/7,054 rows/)).toBeTruthy();
    expect(screen.getByText(/2 cols/)).toBeTruthy();
  });

  it('browses rows for a table, without opening the schema modal', async () => {
    route({
      '/catalog': { body: CATALOG },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    fireEvent.click(
      await screen.findByRole('button', { name: /browse rows/i }),
    );

    expect(await screen.findByText('rows page reached')).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeFalsy();
  });

  it('opens a table and shows every column with its declared type', async () => {
    route({
      '/catalog': { body: CATALOG },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    fireEvent.click(await screen.findByText('purchase_completed'));

    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('user_id');
    expect(dialog.textContent).toContain('String');
    expect(dialog.textContent).toContain('coupon_name');
    expect(dialog.textContent).toContain('Nullable(String)');
    // The sample size behind a statistic travels with it.
    expect(dialog.textContent).toMatch(/of 1,000 sampled/);
  });

  it('says a column was never profiled rather than showing a zero', async () => {
    route({
      '/catalog': { body: CATALOG },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    fireEvent.click(await screen.findByText('purchase_completed'));

    expect((await screen.findByRole('dialog')).textContent).toContain('not profiled');
  });

  it('offers a harvest when the source has never been harvested', async () => {
    route({
      '/catalog': { status: 404, body: { detail: 'Not Found' } },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();

    expect(await screen.findByText(/has not been harvested/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /harvest tables/i })).toBeTruthy();
  });

  it('starts a harvest and follows it', async () => {
    const fetchMock = route({
      '/catalog': { status: 404, body: { detail: 'Not Found' } },
      '/harvests': {
        body: {
          harvest_run_id: '60000000-0000-0000-0000-000000000006',
          data_source_id: SOURCE.data_source_id,
          phase: 'listing_tables',
          tables_found: 3,
          fields_described: 0,
          fields_profiled: 0,
          relations_proposed: 0,
          unreadable_count: 0,
          queries_used: 1,
          queries_budget: 500,
          seconds_used: 0,
        },
      },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /harvest tables/i }));

    await waitFor(() => {
      const posted = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes('/harvests') &&
          (init as RequestInit | undefined)?.method === 'POST',
      );
      expect(posted).toBeTruthy();
    });
  });

  it('toggles a table off from the agent system', async () => {
    const fetchMock = route({
      '/agent-access': {
        body: {
          override_id: '90000000-0000-0000-0000-000000000009',
          data_source_id: SOURCE.data_source_id,
          table_name: 'purchase_completed',
          field_name: null,
          agent_visible: false,
          decided_by: '10000000-0000-0000-0000-000000000001',
          decided_at: '2026-08-01T20:51:00Z',
        },
      },
      '/catalog': { body: CATALOG },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    const toggle = await screen.findByRole('switch');
    fireEvent.click(toggle);

    await waitFor(() => {
      const patched = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes(
            '/sources/40000000-0000-0000-0000-000000000004/tables/purchase_completed/agent-access',
          ) && (init as RequestInit | undefined)?.method === 'PATCH',
      );
      expect(patched).toBeTruthy();
      const body = JSON.parse(
        (patched?.[1] as RequestInit).body as string,
      ) as { agent_visible: boolean };
      expect(body.agent_visible).toBe(false);
    });
  });

  it('toggles one column off without leaving the modal', async () => {
    const fetchMock = route({
      '/agent-access': {
        body: {
          override_id: '90000000-0000-0000-0000-000000000010',
          data_source_id: SOURCE.data_source_id,
          table_name: 'purchase_completed',
          field_name: 'coupon_name',
          agent_visible: false,
          decided_by: '10000000-0000-0000-0000-000000000001',
          decided_at: '2026-08-01T20:51:00Z',
        },
      },
      '/catalog': { body: CATALOG },
      '/v1/connector/sources': { body: [SOURCE] },
    });

    renderPage();
    fireEvent.click(await screen.findByText('purchase_completed'));
    const dialog = await screen.findByRole('dialog');
    const switches = await waitFor(() =>
      dialog.querySelectorAll('[role="switch"]'),
    );
    // Second row is `coupon_name`; the first switch belongs to `user_id`.
    fireEvent.click(switches[1]);

    await waitFor(() => {
      const patched = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes(
            '/tables/purchase_completed/fields/coupon_name/agent-access',
          ) && (init as RequestInit | undefined)?.method === 'PATCH',
      );
      expect(patched).toBeTruthy();
    });
  });
});
