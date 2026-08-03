/**
 * OPFS Metadata Service
 *
 * Service for managing OPFS file metadata in the database.
 * Implements OpfsMetadataOperations interface.
 *
 * @module services/opfs-metadata
 */

import { OPFS_FILE_TYPE } from '@open-zentra/foundation-data-model';

import type { OpfsMetadataEntry, OpfsMetadataOperations } from '../tables/opfs-metadata';
import { sortByDependencies } from '../tables/opfs-metadata';
import { assertValid } from '../validation/assert-valid';
import { opfsMetadataEntrySchema } from '../validation/schemas';
import { BaseService } from './base';

/**
 * OPFS Metadata Service
 * Implements OpfsMetadataOperations
 */
export class OpfsMetadataService extends BaseService implements OpfsMetadataOperations {
  /**
   * Get file metadata by path
   */
  get = async (path: string): Promise<OpfsMetadataEntry | undefined> => {
    return this.db.opfsFiles.get(path);
  };

  /**
   * Set file metadata
   * Validates before write
   */
  set = async (entry: OpfsMetadataEntry): Promise<void> => {
    assertValid(opfsMetadataEntrySchema, entry, 'OpfsMetadataEntry');
    await this.db.opfsFiles.put(entry);
    this.log('OPFS metadata set:', entry.path);
  };

  /**
   * Delete file metadata
   */
  delete = async (path: string): Promise<void> => {
    await this.db.opfsFiles.delete(path);
    this.log('OPFS metadata deleted:', path);
  };

  /**
   * Get all files for a table
   */
  getByTable = async (tableName: string): Promise<OpfsMetadataEntry[]> => {
    return this.db.opfsFiles.where('tableName').equals(tableName).toArray();
  };

  /**
   * Get all registered files
   */
  getRegistered = async (): Promise<OpfsMetadataEntry[]> => {
    return this.db.opfsFiles.where('isRegistered').equals(1).toArray();
  };

  /**
   * Get all view definitions
   */
  getViews = async (): Promise<OpfsMetadataEntry[]> => {
    return this.db.opfsFiles.where('fileType').equals(OPFS_FILE_TYPE.VIEW_DEFINITION).toArray();
  };

  /**
   * Mark file as registered
   */
  markRegistered = async (path: string): Promise<void> => {
    await this.db.opfsFiles.update(path, { isRegistered: true });
    this.log('OPFS file marked registered:', path);
  };

  /**
   * Mark file as unregistered
   */
  markUnregistered = async (path: string): Promise<void> => {
    await this.db.opfsFiles.update(path, { isRegistered: false });
    this.log('OPFS file marked unregistered:', path);
  };

  /**
   * Mark all files as unregistered
   */
  markAllUnregistered = async (): Promise<void> => {
    await this.db.opfsFiles.toCollection().modify({ isRegistered: false });
    this.log('All OPFS files marked unregistered');
  };

  /**
   * Get files in dependency order (topological sort)
   */
  getInDependencyOrder = async (): Promise<OpfsMetadataEntry[]> => {
    const files = await this.getRegistered();
    return sortByDependencies(files);
  };

  /**
   * Get total size of all files
   * Optimized: uses each() to avoid loading all records into memory
   */
  getTotalSize = async (): Promise<number> => {
    let total = 0;
    await this.db.opfsFiles.each((file) => {
      total += file.sizeBytes;
    });
    return total;
  };

  /**
   * Get total count of files
   */
  count = async (): Promise<number> => {
    return this.db.opfsFiles.count();
  };

  /**
   * Check if a file exists
   */
  exists = async (path: string): Promise<boolean> => {
    const entry = await this.db.opfsFiles.get(path);
    return entry !== undefined;
  };

  /**
   * Clear all metadata
   */
  clear = async (): Promise<void> => {
    await this.db.opfsFiles.clear();
    this.log('OPFS metadata cleared');
  };
}
