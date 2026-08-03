# Foundation Sync Engine

`@open-zentra/foundation-sync-engine` coordinates offline mutation replay, conflict resolution, cross-tab leadership, and cache invalidation for API-backed data flows.

## Responsibilities

- Queue offline mutations and replay them with HTTP descriptors
- Resolve conflicts using shared `foundation-data-model` strategies
- Coordinate leader election and invalidation across tabs
- Surface sync lifecycle state to the data-layer

## Public API

```ts
import {
  createSyncCoordinator,
  DEFAULT_MERGE_CONFIG,
  SyncCoordinator,
  type IQueueManager,
} from '@open-zentra/foundation-sync-engine';
```

## Quick Start

```ts
import axios from 'axios';
import { QueryClient } from '@tanstack/react-query';

import { CONFLICT_STRATEGY } from '@open-zentra/foundation-data-model';
import { createSyncCoordinator } from '@open-zentra/foundation-sync-engine';

const coordinator = createSyncCoordinator({
  queryClient: new QueryClient(),
  axiosInstance: axios.create({ baseURL: '/api' }),
  tables,
  conflictStrategy: CONFLICT_STRATEGY.LAST_WRITE_WINS,
  enableCrossTab: true,
  autoStart: true,
});
```

## Configuration

- `queryClient` (required)
- `axiosInstance` (required)
- `tables`
- `database`
- `conflictStrategy`
- `autoStart`
- `enableCrossTab`
- `healthCheckUrl`
- `healthCheckInterval`
- `debug`
- `onError`

## Validation

```bash
./node_modules/.bin/tsc -p libs/foundation/sync-engine/tsconfig.lib.json --pretty false --noEmit
```
