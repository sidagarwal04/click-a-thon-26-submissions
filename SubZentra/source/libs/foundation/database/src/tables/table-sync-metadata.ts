/**
 * Table sync metadata definitions.
 * @module tables/table-sync-metadata
 */

import type { TableSyncMetadataEntry } from '@open-zentra/foundation-data-model';

/**
 * Table sync metadata operations interface
 */
export interface TableSyncMetadataOperations {
  /** Get metadata for a table */
  get(tableName: string): Promise<TableSyncMetadataEntry | undefined>;

  /** Set metadata for a table */
  set(entry: TableSyncMetadataEntry): Promise<void>;

  /** Delete metadata for a table */
  delete(tableName: string): Promise<void>;

  /** Get all metadata entries */
  getAll(): Promise<TableSyncMetadataEntry[]>;

  /** Get multiple entries by table names */
  getMany(tableNames: string[]): Promise<Map<string, TableSyncMetadataEntry | undefined>>;

  /** Check if metadata exists for a table */
  exists(tableName: string): Promise<boolean>;

  /** Clear all metadata */
  clear(): Promise<void>;

  /** Get count of tracked tables */
  count(): Promise<number>;
}
