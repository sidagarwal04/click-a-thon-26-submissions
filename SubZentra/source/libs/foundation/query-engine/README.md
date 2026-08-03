# Foundation Query Engine

`@open-zentra/foundation-query-engine` models queries, compiles analytics SQL, and routes work between DuckDB analytics and API-backed transactional reads and writes.

## Responsibilities

- Query contracts, builders, and presets
- SQL compilation for DuckDB analytics paths
- Routing simple single-table transactional queries to `table.api`
- Routing joins, measures, and multi-table reads to DuckDB
- React hooks that delegate execution to `foundation-data-layer`

## Setup

Wrap your app in `DataLayerProvider` and register tables with `api` descriptors plus optional analytics config.

```tsx
import { DataLayerProvider } from '@open-zentra/foundation-data-layer';

export const AppProviders = ({ children }: { children: React.ReactNode }) => (
  <DataLayerProvider config={{ axiosInstance, websocket, tables }}>{children}</DataLayerProvider>
);
```

## Usage

```tsx
import { useDLQueryEngine } from '@open-zentra/foundation-query-engine';

const result = useDLQueryEngine({
  query: {
    dimensions: [{ member: 'users.name' }],
    filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
  },
});
```

The hook automatically chooses:

- Transactional API path for simple single-table reads
- DuckDB path for joins, measures, and multi-table analytics queries

## Notes

- Mutations always route through the API-backed data-layer mutation hooks
- Transactional query-engine caches are invalidated on relevant realtime events
- Datasource metadata for analytics sync is fetched through `datasourceEndpoint`

## Validation

```bash
./node_modules/.bin/tsc -p libs/foundation/query-engine/tsconfig.lib.json --pretty false --noEmit
```
