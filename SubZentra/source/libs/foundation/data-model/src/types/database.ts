/**
 * Shared database contracts for foundation libraries.
 *
 * These contracts are consumed by foundation-database, sync-engine, bridge,
 * and data-layer to keep database-facing types in one canonical place.
 *
 * @module types/database
 */

import type { DataSourceFileInfo } from '../datasource';
import type { JsonValue } from './json-serializable';
import type { ConflictStrategy } from './sync';
import type { ValueOf } from './utility';

/**
 * Query cache status.
 */
export const QUERY_CACHE_STATUS = {
  FRESH: 'fresh',
  STALE: 'stale',
  EXPIRED: 'expired',
} as const;

export type QueryCacheStatus = ValueOf<typeof QUERY_CACHE_STATUS>;

/**
 * Mutation processing status.
 */
export const MUTATION_STATUS = {
  PENDING: 'pending',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  FAILED: 'failed',
  OFFLINE_QUEUED: 'offline_queued',
} as const;

export type MutationStatus = ValueOf<typeof MUTATION_STATUS>;

/**
 * Mutation operation type.
 */
export const MUTATION_TYPE = {
  CREATE: 'create',
  UPDATE: 'update',
  DELETE: 'delete',
} as const;

export type MutationType = ValueOf<typeof MUTATION_TYPE>;

/**
 * Offline mutation entry persisted in the database queue.
 */
export interface MutationQueueEntry<TPayload = JsonValue> {
  id: string;
  idempotencyKey: string;
  timestamp: number;
  status: MutationStatus;
  type: MutationType;
  tableName: string;
  entityId: string;
  payload: TPayload;
  optimisticData?: TPayload;
  previousData?: TPayload;
  retryCount: number;
  lastError?: string;
  serverId?: string;
  invalidateKeys?: string[];
  dependsOn?: string[];
  conflictStrategy?: ConflictStrategy;
}

/**
 * Input contract used to create a mutation queue entry.
 */
export interface CreateMutationOptions<TPayload = JsonValue> {
  type: MutationType;
  tableName: string;
  entityId: string;
  payload: TPayload;
  optimisticData?: TPayload;
  previousData?: TPayload;
  invalidateKeys?: string[];
  dependsOn?: string[];
  conflictStrategy?: ConflictStrategy;
}

/**
 * OPFS file classification.
 */
export const OPFS_FILE_TYPE = {
  PARQUET: 'parquet',
  JSON: 'json',
  CSV: 'csv',
  VIEW_DEFINITION: 'view_definition',
} as const;

export type OpfsFileType = ValueOf<typeof OPFS_FILE_TYPE>;

/**
 * Persisted sync-state keys used across foundation libraries.
 */
export const SYNC_STATE_KEY = {
  LAST_SYNC: 'lastSync',
  NETWORK_STATUS: 'networkStatus',
  PENDING_COUNT: 'pendingCount',
  DUCKDB_VIEWS: 'duckdbViews',
  SCHEMA_VERSION: 'schemaVersion',
  CONFLICTS: 'conflicts',
  ID_MAPPINGS: 'idMappings',
  REALTIME_CURSORS: 'realtimeCursors',
} as const;

export type SyncStateKey = ValueOf<typeof SYNC_STATE_KEY>;

/**
 * Transaction modes used by the database facade.
 */
export const DATABASE_TRANSACTION_MODE = {
  READ: 'read',
  READ_WRITE: 'read_write',
} as const;

export type DatabaseTransactionMode = ValueOf<typeof DATABASE_TRANSACTION_MODE>;

/**
 * Logical table names used by the database facade transaction helper.
 */
export const DATABASE_TRANSACTION_TABLE = {
  QUERIES: 'queries',
  MUTATIONS: 'mutations',
  SYNC_STATE: 'sync_state',
  OPFS_FILES: 'opfs_files',
  TABLE_SYNC_METADATA: 'table_sync_metadata',
} as const;

export type DatabaseTransactionTable = ValueOf<typeof DATABASE_TRANSACTION_TABLE>;

/**
 * Stored DuckDB view definition.
 */
export interface DuckDBViewDefinition {
  name: string;
  sql: string;
  dependencies: string[];
}

/**
 * Persisted DuckDB view state.
 */
export interface DuckDBViewsValue {
  views: DuckDBViewDefinition[];
  lastUpdatedAt: number;
}

/**
 * Persisted last-sync state.
 */
export interface LastSyncValue {
  timestamp: number;
  tables: Record<string, number>;
}

/**
 * Table-level sync metadata for analytics file sync.
 */
export interface TableSyncMetadataEntry {
  readonly name: string;
  readonly lastIngestedAt: number;
  readonly loadedAt: number;
  readonly fileHashes: Record<string, string>;
  readonly totalSize: number;
  readonly totalRows: number;
}

/**
 * Create a table sync metadata entry.
 */
export const createTableSyncMetadataEntry = (
  name: string,
  lastIngestedAt: number,
  fileHashes: Record<string, string>,
  options?: {
    totalSize?: number;
    totalRows?: number;
  },
): TableSyncMetadataEntry => ({
  name,
  lastIngestedAt,
  loadedAt: Date.now(),
  fileHashes,
  totalSize: options?.totalSize ?? 0,
  totalRows: options?.totalRows ?? 0,
});

/**
 * Determine whether a table should be refreshed from remote state.
 */
export const needsTableUpdate = (
  entry: TableSyncMetadataEntry | null | undefined,
  remoteLastIngestedAt: number,
): boolean => {
  if (!entry) {
    return true;
  }
  return remoteLastIngestedAt > entry.loadedAt;
};

/**
 * Select files that need to be downloaded by comparing remote and local hashes.
 */
export const getFilesNeedingDownload = <
  TFile extends { filename: string; hash?: string } = DataSourceFileInfo,
>(
  localHashes: Record<string, string>,
  remoteFiles: readonly TFile[],
): TFile[] =>
  remoteFiles.filter((file) => {
    const localHash = localHashes[file.filename];
    return !localHash || localHash !== file.hash;
  });
