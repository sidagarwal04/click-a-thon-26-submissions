/// <reference types="vitest/globals" />
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import type { IdentityContext } from '../../types';

import { ConnectionsPage } from './connections-page';
import { ConnectorConfig } from './connector-config';
import { ConnectorPicker } from './connector-picker';

const getToken = async () => 'test-token';

const identity: IdentityContext = {
  user_id: '10000000-0000-0000-0000-000000000001',
  tenant_id: '20000000-0000-0000-0000-000000000002',
  email: 'owner@example.com',
  tenant_name: 'Acme Europe',
  role: 'owner',
};

const renderAt = (path: string, viewer = false) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const who = viewer ? { ...identity, role: 'viewer' } : identity;

  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route
            path="/connections"
            element={<ConnectionsPage getToken={getToken} identity={who} />}
          />
          <Route path="/connections/new" element={<ConnectorPicker />} />
          <Route
            path="/connections/new/:connectorId"
            element={<ConnectorConfig getToken={getToken} identity={who} />}
          />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('Connections', () => {
  it('lists the sources the tenant has registered, with their health', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [
        {
          data_source_id: '40000000-0000-0000-0000-000000000004',
          name: 'Atlys production events',
          kind: 'connected',
          health: 'reachable',
          last_verified_at: '2026-07-30T09:00:00Z',
        },
      ],
    } as Response);

    renderAt('/connections');

    expect(await screen.findByText('Atlys production events')).toBeTruthy();
    expect(screen.getByText('Reachable')).toBeTruthy();
  });

  it('says so plainly when no source is connected', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    renderAt('/connections');

    expect(await screen.findByText(/No sources connected/i)).toBeTruthy();
  });

  it('offers every connector, and marks the unbuilt ones as such', () => {
    renderAt('/connections/new');

    // Named on its tile and again in the footnote below the grid.
    expect(screen.getAllByText('ClickHouse').length).toBeGreaterThan(0);
    expect(screen.getByText('Snowflake')).toBeTruthy();
    expect(screen.getByText('AWS S3')).toBeTruthy();
    // One connector connects; the rest say they do not.
    expect(screen.getAllByText('Connects')).toHaveLength(1);
    expect(screen.getAllByText('Not built').length).toBeGreaterThan(1);
  });

  it('registers a ClickHouse service from the credentials given', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        data_source_id: '40000000-0000-0000-0000-000000000004',
        name: 'Atlys production events',
        kind: 'connected',
        health: 'reachable',
      }),
    } as Response);

    renderAt('/connections/new/clickhouse');

    fireEvent.change(screen.getByLabelText('Connection name'), {
      target: { value: 'Atlys production events' },
    });
    fireEvent.change(screen.getByLabelText('Host'), {
      target: { value: 'ixirbbg74s.ap-south-1.aws.clickhouse.cloud' },
    });
    fireEvent.change(screen.getByLabelText('Database'), { target: { value: 'clickathon' } });
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'default' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });

    fireEvent.click(screen.getByRole('button', { name: /test and save connection/i }));

    // Success navigates to the list, which fetches again — so the registration
    // is found by its verb rather than by being the most recent call.
    const registration = await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
      );
      if (!call) throw new Error('no registration was posted');
      return call as [string, RequestInit];
    });

    expect(registration[0]).toContain('/v1/connector/sources');
    expect(JSON.parse(registration[1].body as string)).toEqual({
      name: 'Atlys production events',
      credentials: {
        host: 'ixirbbg74s.ap-south-1.aws.clickhouse.cloud',
        port: 8443,
        database: 'clickathon',
        username: 'default',
        password: 'secret',
        secure: true,
      },
      store_sample_values: false,
    });
  });

  it('explains a rejected connection in terms of the field to fix', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({ detail: 'authentication_failed' }),
    } as Response);

    renderAt('/connections/new/clickhouse');

    fireEvent.change(screen.getByLabelText('Connection name'), { target: { value: 'Atlys' } });
    fireEvent.change(screen.getByLabelText('Host'), { target: { value: 'host.example' } });
    fireEvent.change(screen.getByLabelText('Database'), { target: { value: 'default' } });
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'default' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /test and save connection/i }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/username and password/i);
    expect(alert.textContent).toMatch(/Nothing was saved/i);
  });

  it('gives an unbuilt connector a page with no credential fields', () => {
    renderAt('/connections/new/snowflake');

    expect(screen.getByText(/The Snowflake connector is not built/i)).toBeTruthy();
    expect(screen.queryByLabelText('Password')).toBeNull();
  });

  it('keeps a viewer out of registering a source', () => {
    renderAt('/connections/new/clickhouse', true);

    const save = screen.getByRole('button', { name: /test and save connection/i });
    expect(save.hasAttribute('disabled')).toBe(true);
  });
});
