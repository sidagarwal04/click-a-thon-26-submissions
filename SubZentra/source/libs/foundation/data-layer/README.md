# Foundation Data Layer

`@open-zentra/foundation-data-layer` is the client runtime for transactional HTTP APIs, realtime WebSocket events, offline cache persistence, and optional DuckDB analytics.

## What It Provides

- TanStack Query orchestration for HTTP reads and writes
- Offline-first optimistic mutations with queue replay
- IndexedDB-backed query caching
- Table registry shared with sync-engine and query-engine
- Native WebSocket client plus `useRealtimeSocket`
- Background Parquet metadata sync for analytics tables

## Installation

```bash
npm install @open-zentra/foundation-data-layer @tanstack/react-query axios
```

## Quick Start

```tsx
import axios from 'axios';
import { z } from 'zod';

import { createRealtimeTicketFetcher } from '@open-zentra/foundation-auth';
import { DataLayerProvider } from '@open-zentra/foundation-data-layer';
import {
  CONFLICT_STRATEGY,
  DATA_FRESHNESS,
  type UnifiedTableConfig,
} from '@open-zentra/foundation-data-model';

const axiosInstance = axios.create({ baseURL: '/api' });

const tables: ReadonlyArray<UnifiedTableConfig> = [
  {
    name: 'events',
    api: {
      list: { path: '/events' },
      get: { path: ({ id }: { id: string }) => `/events/${id}` },
      create: { method: 'POST', path: '/events', body: (args) => args },
      update: {
        method: 'PATCH',
        path: ({ id }: { id: string }) => `/events/${id}`,
        body: ({ id, ...payload }: { id: string; [key: string]: unknown }) => payload,
      },
      delete: { method: 'DELETE', path: ({ id }: { id: string }) => `/events/${id}` },
    },
    realtime: {
      topic: 'events',
      events: ['created', 'updated', 'deleted', 'snapshot'],
      entitySchema: z.object({ id: z.string(), type: z.string() }),
      snapshotSchema: z.array(z.object({ id: z.string(), type: z.string() })),
      versionField: 'version',
      applyStrategy: 'patch_list',
    },
    analytics: {
      enabled: true,
      freshness: DATA_FRESHNESS.NEAR_REALTIME,
    },
  },
];

export const AppProviders = ({ children }: { children: React.ReactNode }) => (
  <DataLayerProvider
    config={{
      axiosInstance,
      websocket: {
        url: 'wss://example.com/realtime',
        protocolVersion: '1.0',
        auth: {
          mode: 'ticket',
          getTicket: createRealtimeTicketFetcher(axiosInstance, {
            path: '/auth/realtime-ticket',
          }),
        },
        heartbeat: {
          intervalMs: 15000,
          timeoutMs: 45000,
        },
        resume: {
          enabled: true,
          persistCursors: true,
        },
        leaderMode: 'sync-engine',
      },
      conflictStrategy: CONFLICT_STRATEGY.LAST_WRITE_WINS,
      enableCrossTab: true,
      enableAnalytics: true,
      datasourceEndpoint: {
        path: '/datasource/tables',
        params: ({ tables }: { tables: string[] }) => ({ tables }),
      },
      tables,
    }}
  >
    {children}
  </DataLayerProvider>
);
```

## Configuration

`DataLayerConfig`:

- `axiosInstance` (required)
- `websocket` (required, ticket auth only)
- `tables`
- `datasourceEndpoint`
- `conflictStrategy`
- `enableCrossTab`
- `enableAnalytics`
- `defaultStaleTime`
- `defaultGcTime`
- `cache`
- `debug`
- `onSyncError`

`websocket.auth` is required and must use `mode: 'ticket'`. Same-origin cookie deployments still work by fetching the realtime ticket over authenticated HTTP.

## Public API

- `DataLayerProvider`
- `useDataLayer`
- `useDataLayerInternals`
- `useDLGet` / `useDLGetList` / `useDLGetOne`
- `useDLCreate` / `useDLUpdate` / `useDLDelete`
- `useDLAnalytics`
- `useDLAnalyticsMutation`
- `useBackgroundFileSync`
- `useSyncStatus`
- `useConflictResolution`
- `useRealtimeSocket`

## Validation

```bash
./node_modules/.bin/tsc -p libs/foundation/data-model/tsconfig.lib.json --pretty false --noEmit
./node_modules/.bin/tsc -p libs/foundation/data-layer/tsconfig.lib.json --pretty false --noEmit
```
