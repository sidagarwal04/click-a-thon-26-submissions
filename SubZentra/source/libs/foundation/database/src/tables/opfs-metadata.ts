/**
 * OPFS metadata table definitions
 * @module tables/opfs-metadata
 */

import type { OpfsFileType } from '@open-zentra/foundation-data-model';
import { hasCircularDependency, topologicalSort } from '@open-zentra/foundation-utils';

/**
 * OPFS file metadata entry
 */
export interface OpfsMetadataEntry {
  /** File path in OPFS (primary key) */
  path: string;
  /** Associated table/entity name */
  tableName: string;
  /** File type */
  fileType: OpfsFileType;
  /** File size in bytes */
  sizeBytes: number;
  /** Last modified timestamp */
  lastModified: number;
  /** Content hash for change detection */
  contentHash?: string;
  /** Row count (for data files) */
  rowCount?: number;
  /** Schema info (for data files) */
  schema?: OpfsFileSchema;
  /** Whether file is currently registered in DuckDB */
  isRegistered: boolean;
  /** DuckDB view name if this is a view definition */
  viewName?: string;
  /** Dependencies (other files this depends on) */
  dependencies?: string[];
}

/**
 * Schema information for data files
 */
export interface OpfsFileSchema {
  columns: Array<{
    name: string;
    type: string;
    nullable: boolean;
  }>;
}

/**
 * Options for creating OPFS metadata
 */
export interface CreateOpfsMetadataOptions {
  tableName: string;
  fileType: OpfsFileType;
  sizeBytes: number;
  contentHash?: string;
  rowCount?: number;
  schema?: OpfsFileSchema;
  viewName?: string;
  dependencies?: string[];
}

/**
 * Create OPFS metadata entry
 */
export const createOpfsMetadata = (
  path: string,
  options: CreateOpfsMetadataOptions,
): OpfsMetadataEntry => {
  return {
    path,
    tableName: options.tableName,
    fileType: options.fileType,
    sizeBytes: options.sizeBytes,
    lastModified: Date.now(),
    contentHash: options.contentHash,
    rowCount: options.rowCount,
    schema: options.schema,
    isRegistered: false,
    viewName: options.viewName,
    dependencies: options.dependencies,
  };
};

/**
 * OPFS metadata operations interface
 */
export interface OpfsMetadataOperations {
  /** Get file metadata by path */
  get(path: string): Promise<OpfsMetadataEntry | undefined>;
  /** Set file metadata */
  set(entry: OpfsMetadataEntry): Promise<void>;
  /** Delete file metadata */
  delete(path: string): Promise<void>;
  /** Get all files for a table */
  getByTable(tableName: string): Promise<OpfsMetadataEntry[]>;
  /** Get all registered files */
  getRegistered(): Promise<OpfsMetadataEntry[]>;
  /** Get all view definitions */
  getViews(): Promise<OpfsMetadataEntry[]>;
  /** Mark file as registered */
  markRegistered(path: string): Promise<void>;
  /** Mark file as unregistered */
  markUnregistered(path: string): Promise<void>;
  /** Mark all files as unregistered (e.g., after DuckDB restart) */
  markAllUnregistered(): Promise<void>;
  /** Get files in topological order (respecting dependencies) */
  getInDependencyOrder(): Promise<OpfsMetadataEntry[]>;
  /** Get total size of all files */
  getTotalSize(): Promise<number>;
  /** Get total count of files */
  count(): Promise<number>;
  /** Check if file metadata exists */
  exists(path: string): Promise<boolean>;
  /** Clear all file metadata */
  clear(): Promise<void>;
}

/**
 * Sort files by dependencies (topological sort)
 * Throws an error if circular dependencies are detected
 *
 * Uses topologicalSort from foundation-utils for consistent implementation
 * across the codebase.
 */
export const sortByDependencies = (files: OpfsMetadataEntry[]): OpfsMetadataEntry[] => {
  // Check for circular dependencies first
  const hasCycle = hasCircularDependency(
    files,
    (f) => f.path,
    (f) => f.dependencies ?? [],
  );

  if (hasCycle) {
    throw new Error('Circular dependency detected in OPFS files');
  }

  // Perform topological sort using foundation-utils
  return topologicalSort(
    files,
    (f) => f.path,
    (f) => f.dependencies ?? [],
  );
};
