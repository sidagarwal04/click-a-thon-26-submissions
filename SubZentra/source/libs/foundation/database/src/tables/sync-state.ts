/**
 * Sync state table definitions
 * @module tables/sync-state
 */

import type { ZodSchema } from 'zod';

import type {
  DuckDBViewsValue,
  LastSyncValue,
  NetworkStatus,
  RealtimeCursorStore,
  SyncStateKey,
} from '@open-zentra/foundation-data-model';

import {
  duckDBViewsValueSchema,
  lastSyncValueSchema,
  networkStatusSchema,
  realtimeCursorStoreSchema,
} from '../validation/schemas';

/**
 * Sync state entry (key-value store)
 * @template TValue - Type of the state value (defaults to JsonValue)
 */
export interface SyncStateEntry<TValue = unknown> {
  /** State key */
  key: string;
  /** State value (serialized) */
  value: TValue;
  /** Last updated timestamp */
  updatedAt: number;
}

// NOTE: NetworkStatus should be imported directly from @open-zentra/foundation-data-model
// Do NOT re-export it here to maintain single source of truth

/**
 * Create sync state entry (const arrow function pattern)
 * @template TValue - Type of the state value
 */
export const createSyncStateEntry = <TValue = unknown>(
  key: SyncStateKey,
  value: TValue,
): SyncStateEntry<TValue> => ({
  key,
  value,
  updatedAt: Date.now(),
});

/**
 * Options for getting state value with schema validation
 */
export interface GetSyncStateOptions<T> {
  /** Zod schema for runtime validation (required for type-safe return) */
  schema: ZodSchema<T>;
}

/**
 * Sync state operations interface
 */
export interface SyncStateOperations {
  /** Get state value by key with Zod schema validation */
  get<T>(key: SyncStateKey, options: GetSyncStateOptions<T>): Promise<T | undefined>;
  /** Get raw state value by key without type validation */
  getRaw(key: SyncStateKey): Promise<unknown>;
  /** Set state value */
  set<TValue>(key: SyncStateKey, value: TValue): Promise<void>;
  /** Delete state entry */
  delete(key: SyncStateKey): Promise<void>;
  /** Get all state entries */
  getAll(): Promise<SyncStateEntry[]>;
  /** Clear all state */
  clear(): Promise<void>;

  // Typed convenience methods for common state keys
  /** Get last sync value with type validation */
  getLastSync(): Promise<LastSyncValue | undefined>;
  /** Set last sync value */
  setLastSync(value: LastSyncValue): Promise<void>;
  /** Get network status with type validation */
  getNetworkStatus(): Promise<NetworkStatus | undefined>;
  /** Set network status */
  setNetworkStatus(value: NetworkStatus): Promise<void>;
  /** Get DuckDB views with type validation */
  getDuckDBViews(): Promise<DuckDBViewsValue | undefined>;
  /** Set DuckDB views */
  setDuckDBViews(value: DuckDBViewsValue): Promise<void>;
  /** Get pending mutation count */
  getPendingCount(): Promise<number>;
  /** Set pending mutation count */
  setPendingCount(count: number): Promise<void>;
  /** Get schema version */
  getSchemaVersion(): Promise<number>;
  /** Set schema version */
  setSchemaVersion(version: number): Promise<void>;
  /** Get realtime topic cursors */
  getRealtimeCursors(): Promise<RealtimeCursorStore | undefined>;
  /** Set realtime topic cursors */
  setRealtimeCursors(value: RealtimeCursorStore): Promise<void>;
}

/**
 * Default network status
 */
export const DEFAULT_NETWORK_STATUS: NetworkStatus = {
  isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
  lastOnlineAt: null,
  lastOfflineAt: null,
};

/**
 * Default DuckDB views state
 */
export const DEFAULT_DUCKDB_VIEWS: DuckDBViewsValue = {
  views: [],
  lastUpdatedAt: 0,
};

/**
 * Type guard for LastSyncValue using Zod schema validation
 * Provides full validation of all fields, not just existence checks
 */
export const isLastSyncValue = (value: unknown): value is LastSyncValue => {
  return lastSyncValueSchema.safeParse(value).success;
};

/**
 * Type guard for NetworkStatus using Zod schema validation
 * Provides full validation of all fields, not just existence checks
 */
export const isNetworkStatus = (value: unknown): value is NetworkStatus => {
  return networkStatusSchema.safeParse(value).success;
};

/**
 * Type guard for DuckDBViewsValue using Zod schema validation
 * Provides full validation of all fields, not just existence checks
 */
export const isDuckDBViewsValue = (value: unknown): value is DuckDBViewsValue => {
  return duckDBViewsValueSchema.safeParse(value).success;
};

/**
 * Type guard for RealtimeCursorStore using Zod schema validation.
 */
export const isRealtimeCursorStore = (value: unknown): value is RealtimeCursorStore => {
  return realtimeCursorStoreSchema.safeParse(value).success;
};

// NOTE: SYNC_STATE_KEYS is NOT re-exported here.
// Import it from '../core/config' (single source of truth)
