/**
 * Sync State Service
 *
 * Service for managing sync state in the database.
 * Implements SyncStateOperations interface with type-safe convenience methods.
 *
 * @module services/sync-state
 */

import type { ZodSchema } from 'zod';
import { z } from 'zod';

import {
  SYNC_STATE_KEY,
  type DuckDBViewsValue,
  type LastSyncValue,
  type NetworkStatus,
  type RealtimeCursorStore,
  type SyncStateKey,
} from '@open-zentra/foundation-data-model';

import type { SyncStateEntry, SyncStateOperations } from '../tables/sync-state';
import { assertValid } from '../validation/assert-valid';
import {
  duckDBViewsValueSchema,
  lastSyncValueSchema,
  networkStatusSchema,
  realtimeCursorStoreSchema,
  syncStateEntrySchema,
} from '../validation/schemas';
import { BaseService } from './base';

// Simple schemas for primitive values
const numberSchema = z.number();

/**
 * Options for getting state value with schema validation
 */
export interface GetStateOptions<T> {
  /** Zod schema for runtime validation (required for type-safe return) */
  schema: ZodSchema<T>;
}

/**
 * Sync State Service
 * Implements SyncStateOperations with type-safe convenience methods
 */
export class SyncStateService extends BaseService implements SyncStateOperations {
  /**
   * Get state value by key with runtime validation
   *
   * @param key - The sync state key
   * @param options - Options with Zod schema for runtime validation
   * @returns The validated value if found and valid, undefined otherwise
   */
  get = async <T>(key: SyncStateKey, options: GetStateOptions<T>): Promise<T | undefined> => {
    const entry = await this.db.syncState.get(key);
    if (!entry) return undefined;

    // Validate the value with provided schema
    const result = options.schema.safeParse(entry.value);
    if (!result.success) {
      this.log(`Validation failed for key "${key}":`, result.error.message);
      return undefined;
    }
    return result.data;
  };

  /**
   * Get raw state value by key without type validation
   *
   * Use this when you don't need type safety or when working with dynamic keys.
   * For type-safe access, use get() with a schema or the typed convenience methods.
   *
   * @param key - The sync state key
   * @returns The raw value if found, undefined otherwise
   */
  getRaw = async (key: SyncStateKey): Promise<unknown> => {
    const entry = await this.db.syncState.get(key);
    if (!entry) return undefined;
    return entry.value;
  };

  /**
   * Set state value with validation
   */
  set = async <TValue>(key: SyncStateKey, value: TValue): Promise<void> => {
    const entry: SyncStateEntry<TValue> = {
      key,
      value,
      updatedAt: Date.now(),
    };

    assertValid(syncStateEntrySchema, entry, 'SyncStateEntry');
    await this.db.syncState.put(entry);
    this.log('Sync state set:', key);
  };

  /**
   * Delete state entry
   */
  delete = async (key: SyncStateKey): Promise<void> => {
    await this.db.syncState.delete(key);
    this.log('Sync state deleted:', key);
  };

  /**
   * Get all state entries
   */
  getAll = async (): Promise<SyncStateEntry[]> => {
    return this.db.syncState.toArray();
  };

  /**
   * Clear all state
   */
  clear = async (): Promise<void> => {
    await this.db.syncState.clear();
    this.log('Sync state cleared');
  };

  // =========================================================================
  // Type-safe convenience methods with Zod schema validation
  // =========================================================================

  /**
   * Get last sync value with Zod schema validation
   */
  getLastSync = async (): Promise<LastSyncValue | undefined> => {
    return this.get(SYNC_STATE_KEY.LAST_SYNC, { schema: lastSyncValueSchema });
  };

  /**
   * Set last sync value
   */
  setLastSync = async (value: LastSyncValue): Promise<void> => {
    await this.set(SYNC_STATE_KEY.LAST_SYNC, value);
  };

  /**
   * Get network status with Zod schema validation
   */
  getNetworkStatus = async (): Promise<NetworkStatus | undefined> => {
    return this.get(SYNC_STATE_KEY.NETWORK_STATUS, { schema: networkStatusSchema });
  };

  /**
   * Set network status
   */
  setNetworkStatus = async (value: NetworkStatus): Promise<void> => {
    await this.set(SYNC_STATE_KEY.NETWORK_STATUS, value);
  };

  /**
   * Get DuckDB views with Zod schema validation
   */
  getDuckDBViews = async (): Promise<DuckDBViewsValue | undefined> => {
    return this.get(SYNC_STATE_KEY.DUCKDB_VIEWS, { schema: duckDBViewsValueSchema });
  };

  /**
   * Set DuckDB views
   */
  setDuckDBViews = async (value: DuckDBViewsValue): Promise<void> => {
    await this.set(SYNC_STATE_KEY.DUCKDB_VIEWS, value);
  };

  /**
   * Get pending count with Zod schema validation
   */
  getPendingCount = async (): Promise<number> => {
    const value = await this.get(SYNC_STATE_KEY.PENDING_COUNT, { schema: numberSchema });
    return value ?? 0;
  };

  /**
   * Set pending count
   */
  setPendingCount = async (count: number): Promise<void> => {
    await this.set(SYNC_STATE_KEY.PENDING_COUNT, count);
  };

  /**
   * Get schema version with Zod schema validation
   */
  getSchemaVersion = async (): Promise<number> => {
    const value = await this.get(SYNC_STATE_KEY.SCHEMA_VERSION, { schema: numberSchema });
    return value ?? 1;
  };

  /**
   * Set schema version
   */
  setSchemaVersion = async (version: number): Promise<void> => {
    await this.set(SYNC_STATE_KEY.SCHEMA_VERSION, version);
  };

  /**
   * Get realtime cursor store with Zod schema validation
   */
  getRealtimeCursors = async (): Promise<RealtimeCursorStore | undefined> => {
    return this.get(SYNC_STATE_KEY.REALTIME_CURSORS, { schema: realtimeCursorStoreSchema });
  };

  /**
   * Set realtime cursor store
   */
  setRealtimeCursors = async (value: RealtimeCursorStore): Promise<void> => {
    await this.set(SYNC_STATE_KEY.REALTIME_CURSORS, value);
  };
}
