---
name: Offline-First Sync Engine
overview: ''
todos: []
---

# Offline-First Sync Engine Architecture

## Executive Summary

This architecture delivers a **Linear-style offline-first sync engine** that:

- Works **fully offline** with deterministic local state
- Uses **Convex as the authoritative backend** with TanStack Query orchestration
- Provides **dual DuckDB execution** (Native via Electron IPC, WASM fallback)
- Caches **Parquet files in OPFS** for offline analytics
- Exposes clean hooks: `useDLCreate`, `useDLUpdate`, `useDLDelete`, `useDLGet`, `useDLAnalytics`

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph ReactApp [React Application Layer]
        Hooks[useDLCreate / useDLUpdate / useDLDelete / useDLGet / useDLAnalytics]
    end

    subgraph TanStackQuery [TanStack Query Layer]
        QueryClient[QueryClient]
        ConvexQueryClient[ConvexQueryClient]
        Mutations[Mutation Queue]
        Cache[Query Cache]
    end

    subgraph SyncEngine [foundation/sync-engine]
        OfflineQueue[Offline Operation Queue]
        Reconciler[Server Reconciler]
        OptimisticStore[Optimistic State Manager]
    end

    subgraph DataLayer [foundation/data-layer]
        Persistence[Dexie/IndexedDB]
        EntityStore[Entity Store]
    end

    subgraph Bridge [foundation/bridge]
        Detection[Environment Detector]
        Router[Query Router]
        IPCClient[IPC Client]
        WASMManager[WASM Lifecycle Manager]
    end

    subgraph Analytics [Analytics Layer]
        OPFSCache[OPFS File Cache]
        MetadataStore[File Metadata Store]
        DuckDBNative[DuckDB Native - Electron]
        DuckDBWASM[DuckDB WASM - Browser]
    end

    subgraph Convex [Convex Backend]
        ConvexClient[ConvexReactClient]
        ReactiveQueries[Reactive Subscriptions]
        ServerMutations[Server Mutations]
    end

    Hooks --> QueryClient
    QueryClient --> ConvexQueryClient
    ConvexQueryClient --> ConvexClient
    ConvexClient --> ReactiveQueries
    ConvexClient --> ServerMutations

    QueryClient --> SyncEngine
    SyncEngine --> OfflineQueue
    SyncEngine --> OptimisticStore
    OfflineQueue --> Persistence
    OptimisticStore --> EntityStore

    Hooks --> Bridge
    Bridge --> Detection
    Detection --> Router
    Router --> IPCClient
    Router --> WASMManager
    IPCClient --> DuckDBNative
    WASMManager --> DuckDBWASM
    WASMManager --> OPFSCache
    OPFSCache --> MetadataStore
    MetadataStore --> Persistence
```

---

## Foundation Layer Architecture

### 1. `foundation/data-model` (Existing - Extend)

Canonical type definitions shared across all layers:

```typescript
// Entity base types
interface BaseEntity {
  id: string;
  _creationTime: number;
  _updatedTime: number;
}

// Analytics query types
interface AnalyticsQuery {
  tables: string[];
  sql: string;
  params?: Record<string, unknown>;
}
interface AnalyticsQueryKey {
  type: 'analytics';
  tables: string[];
  queryHash: string;
}

// Sync metadata types
interface SyncMetadata {
  localVersion: number;
  serverVersion: number;
  pendingOps: number;
}
```

### 2. `foundation/database` (Rewrite)

Dexie-based persistence for:

- **Entity storage** (offline cache of Convex data)
- **Pending operations queue** (offline mutations)
- **File metadata** (Parquet file registry for DuckDB)
- **Sync cursors** (last sync timestamps per entity type)

Key stores:

```
_entities: id, type, data, localVersion, serverVersion, syncStatus
_pendingOps: ++localId, entityType, entityId, mutation, args, createdAt, retries
_fileMetadata: fileId, logicalTable, schema, partitionKey, fileSize, lastModified
_syncCursors: entityType, cursor, lastSyncAt
```

### 3. `foundation/sync-engine` (New - Core Implementation)

The heart of offline-first sync:

```mermaid
sequenceDiagram
    participant App as React App
    participant TQ as TanStack Query
    participant SE as Sync Engine
    participant DB as Dexie
    participant Convex as Convex Backend

    Note over App,Convex: Online Flow
    App->>TQ: useDLCreate(data)
    TQ->>SE: queueMutation()
    SE->>DB: persistOptimistic()
    SE->>TQ: updateCache(optimistic)
    SE->>Convex: mutation()
    Convex-->>SE: result
    SE->>DB: confirmMutation()
    SE->>TQ: invalidateQueries()

    Note over App,Convex: Offline Flow
    App->>TQ: useDLCreate(data)
    TQ->>SE: queueMutation()
    SE->>DB: persistPending()
    SE->>TQ: updateCache(optimistic)
    Note over SE: Queued for later

    Note over App,Convex: Reconnection
    SE->>DB: getPendingOps()
    loop Each pending op
        SE->>Convex: mutation()
        Convex-->>SE: result/conflict
        SE->>DB: resolveMutation()
    end
    SE->>TQ: invalidateQueries()
```

**Key Responsibilities:**

- Offline operation queue management
- Optimistic update application
- Server reconciliation (server-authoritative)
- Conflict detection and resolution
- TanStack Query cache coordination

### 4. `foundation/bridge` (New - DuckDB Abstraction)

Environment-agnostic analytics execution:

```mermaid
flowchart LR
    subgraph Bridge [Query Router]
        Detect[Environment Detection]
        Route[Execution Router]
    end

    subgraph Native [Electron Path]
        IPC[IPC Invoke]
        Stream[MessagePort Stream]
        NativeDuck[DuckDB Native]
    end

    subgraph WASM [Browser Path]
        Lifecycle[Lifecycle Manager]
        Hydrate[View Hydrator]
        WASMDuck[DuckDB WASM]
    end

    subgraph Storage [OPFS Storage]
        Files[Parquet Files]
        Meta[File Metadata]
    end

    Detect --> Route
    Route -->|Electron Available| IPC
    Route -->|Electron Available + Large Result| Stream
    Route -->|Browser Only| Lifecycle
    IPC --> NativeDuck
    Stream --> NativeDuck
    Lifecycle --> Hydrate
    Hydrate --> WASMDuck
    WASMDuck --> Files
    Files --> Meta
```

**Key Features:**

- **Environment detection**: Check for Electron IPC availability
- **Query routing**: Native DuckDB preferred, WASM fallback
- **IPC modes**: `invoke` for simple queries, `MessagePort` for streaming
- **WASM lifecycle**: 30s idle shutdown, deterministic rehydration
- **OPFS management**: File caching, metadata persistence

---

## Data Flow Architecture

### CRUD Operations (Convex-backed)

```mermaid
flowchart TB
    subgraph Hooks [Data Layer Hooks]
        Create[useDLCreate]
        Update[useDLUpdate]
        Delete[useDLDelete]
        Get[useDLGet]
    end

    subgraph TanStack [TanStack Query]
        MutationFn[useMutation + useConvexMutation]
        QueryFn[useQuery + convexQuery]
        OptUpdate[Optimistic Update]
        Invalidate[Query Invalidation]
    end

    subgraph Sync [Sync Engine]
        Queue[Operation Queue]
        Persist[Dexie Persistence]
        Reconcile[Server Reconciliation]
    end

    subgraph Backend [Convex]
        ConvexMut[Convex Mutations]
        ConvexQuery[Convex Queries]
        Reactive[Reactive Updates]
    end

    Create --> MutationFn
    Update --> MutationFn
    Delete --> MutationFn
    Get --> QueryFn

    MutationFn --> OptUpdate
    OptUpdate --> Queue
    Queue --> Persist
    MutationFn --> ConvexMut
    ConvexMut --> Reconcile
    Reconcile --> Invalidate

    QueryFn --> ConvexQuery
    ConvexQuery --> Reactive
    Reactive --> Invalidate
```

### Analytics Queries (DuckDB-backed)

```mermaid
flowchart TB
    subgraph Hook [useDLAnalytics]
        QueryKey[Deterministic Query Key]
        TQQuery[TanStack useQuery]
    end

    subgraph Cache [TanStack Cache]
        CacheKey["['analytics', 'tables:X,Y', 'hash:abc']"]
        CacheData[Cached Result]
    end

    subgraph Bridge [Bridge Layer]
        Router[Query Router]
        EnvCheck{Electron?}
    end

    subgraph Native [Native Path]
        IPCInvoke[IPC Invoke]
        IPCStream[MessagePort]
        NativeDuck[DuckDB Native]
    end

    subgraph WASM [WASM Path]
        WASMStart[Start WASM]
        ViewHydrate[Hydrate Views]
        WASMDuck[DuckDB WASM]
        OPFSRead[Read OPFS Files]
    end

    Hook --> QueryKey
    QueryKey --> TQQuery
    TQQuery --> CacheKey
    CacheKey -->|Miss| Router
    Router --> EnvCheck
    EnvCheck -->|Yes| IPCInvoke
    EnvCheck -->|Yes + Large| IPCStream
    EnvCheck -->|No| WASMStart
    IPCInvoke --> NativeDuck
    IPCStream --> NativeDuck
    WASMStart --> ViewHydrate
    ViewHydrate --> OPFSRead
    OPFSRead --> WASMDuck
    NativeDuck --> CacheData
    WASMDuck --> CacheData
    CacheData --> TQQuery
```

---

## Hook API Design

### Core CRUD Hooks

```typescript
// useDLGet - Read single entity or list
const { data, isLoading, error } = useDLGet<User>('users', userId);
const { data: users } = useDLGet<User[]>('users', {
  filter: { role: 'admin' },
});

// useDLCreate - Create with optimistic update
const { mutate: create, isPending } = useDLCreate<User>('users');
create({ name: 'John', email: 'john@example.com' });

// useDLUpdate - Update with optimistic update
const { mutate: update, isPending } = useDLUpdate<User>('users');
update({ id: userId, name: 'Jane' });

// useDLDelete - Delete with optimistic update
const { mutate: remove, isPending } = useDLDelete('users');
remove(userId);
```

### Analytics Hook

```typescript
// useDLAnalytics - Query DuckDB with TanStack Query caching
const { data, isLoading, error } = useDLAnalytics({
  tables: ['events', 'users'],
  sql: 'SELECT COUNT(*) FROM events e JOIN users u ON e.user_id = u.id WHERE u.role = ?',
  params: { role: 'admin' },
  // Invalidation happens via table names
});

// useDLAnalyticsMutation - For analytical writes (rare)
const { mutate } = useDLAnalyticsMutation();
mutate({
  sql: 'INSERT INTO analytics_cache ...',
  invalidateTables: ['analytics_cache'],
});
```

---

## Query Key Strategy (Critical)

All analytics queries MUST have deterministic query keys:

```typescript
// Query key structure
type AnalyticsQueryKey = [
  'analytics', // Namespace
  `tables:${string}`, // Logical table dependencies (sorted)
  `query:${string}`, // Query identity hash
];

// Example
['analytics', 'tables:events,users', 'query:session_duration_v3'];

// Invalidation by table
queryClient.invalidateQueries({ queryKey: ['analytics', 'tables:events'] });

// Invalidation by exact query
queryClient.invalidateQueries({
  queryKey: ['analytics', 'tables:events,users', 'query:session_duration_v3'],
});
```

---

## Libraries to Generate

Using `npx nx generate @nx/react:library`:

| Library | Directory | Tags | Purpose |

|---------|-----------|------|---------|

| `foundation-sync-engine` | `libs/foundation/sync-engine` | `foundation:sync-engine` | Offline-first sync orchestration |

| `foundation-bridge` | `libs/foundation/bridge` | `foundation:bridge` | DuckDB execution abstraction |

**Note:** `foundation/data-layer` and `foundation/database` will be **rewritten** to integrate with the new architecture.

---

## ESLint Module Boundary Updates

Add to [`eslint.config.mjs`](eslint.config.mjs):

```javascript

// foundation:sync-engine -> Can import data-layer, database, utils, data-model, trackers

{

sourceTag: 'foundation:sync-engine',

onlyDependOnLibsWithTags: [

'foundation:sync-engine',

'foundation:data-layer',

'foundation:database',

'foundation:utils',

'foundation:data-model',

'foundation:trackers',

],

},

// foundation:bridge -> Can import database, utils, data-model, trackers

{

sourceTag: 'foundation:bridge',

onlyDependOnLibsWithTags: [

'foundation:bridge',

'foundation:database',

'foundation:utils
```
