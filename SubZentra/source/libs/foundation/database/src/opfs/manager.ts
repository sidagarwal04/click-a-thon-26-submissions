/**
 * OPFS (Origin Private File System) Manager
 *
 * Manages files in Origin Private File System with quota handling,
 * proper error types, and metadata tracking.
 *
 * @module opfs/manager
 */

import isEqual from 'fast-deep-equal';

import {
  type LegacyErrorCallback,
  type OpfsFileType,
} from '@open-zentra/foundation-data-model';
import {
  clearDirectory,
  createDebugLogger,
  createDeepEqualComparison,
  createDirectoryPath,
  createSingletonFactory,
  fileExistsInOpfs,
  getDirectoryAtPath,
  getErrorMessage,
  getOpfsRootDirectory,
  isOpfsSupported,
  listDirectoryEntries,
  normalizeError,
  type Logger,
} from '@open-zentra/foundation-utils';

import type { InsightsDatabase } from '../core/database';
import { getDatabase } from '../core/database';
import {
  createOpfsInitFailedError,
  createOpfsNotSupportedError,
  createQuotaExceededError,
  createValidationError,
  isQuotaExceededError,
} from '../errors/database-errors';
import { OpfsMetadataService } from '../services/opfs-metadata';
import {
  createOpfsMetadata,
  type OpfsFileSchema,
  type OpfsMetadataEntry,
} from '../tables/opfs-metadata';

/**
 * Default error handler that logs to console.error
 */
const defaultErrorHandler: LegacyErrorCallback = (error: Error, context?: string): void => {
  console.error(`[OpfsManager] Error in ${context ?? 'unknown'}:`, error.message);
};

// Note: Type augmentation for FileSystemDirectoryHandle is now in foundation-utils/opfs

/**
 * OPFS Manager configuration
 */
export interface OpfsManagerConfig {
  /** Database instance */
  database?: InsightsDatabase;
  /** Root directory name in OPFS */
  rootDir?: string;
  /** Enable debug logging */
  debug?: boolean;
  /** Custom error handler for non-fatal errors */
  onError?: LegacyErrorCallback;
}

/**
 * Default OPFS manager configuration
 */
const DEFAULT_CONFIG: Required<Omit<OpfsManagerConfig, 'database' | 'onError'>> = {
  rootDir: 'open-zentra',
  debug: false,
};

/**
 * File write options
 */
export interface WriteFileOptions {
  tableName: string;
  fileType: OpfsFileType;
  contentHash?: string;
  rowCount?: number;
  schema?: OpfsFileSchema;
  viewName?: string;
  dependencies?: string[];
}

/**
 * OPFS Manager for managing files in Origin Private File System
 */
export class OpfsManager {
  private db: InsightsDatabase;
  private config: Required<Omit<OpfsManagerConfig, 'database' | 'onError'>>;
  private rootHandle: FileSystemDirectoryHandle | null = null;
  private initialized = false;
  private onError: LegacyErrorCallback;
  private logger: Logger;
  private metadataService: OpfsMetadataService;

  constructor(config: OpfsManagerConfig = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.db = config.database ?? getDatabase();
    // Use provided error handler or fall back to default
    this.onError = config.onError ?? defaultErrorHandler;
    // Use foundation/utils logger
    this.logger = createDebugLogger('OpfsManager', this.config.debug);
    this.metadataService = new OpfsMetadataService(this.db, this.db.config);
  }

  /**
   * Log helper using foundation/utils logger
   */
  private log = (...args: unknown[]): void => {
    this.logger.debug(...args);
  };

  /**
   * Handle non-fatal errors using configured handler
   */
  private handleNonFatalError = (error: unknown, context: string): void => {
    const err = normalizeError(error);
    this.onError(err, context);
  };

  /**
   * Check if OPFS is supported in this environment
   */
  static isSupported = (): boolean => {
    return isOpfsSupported();
  };

  /**
   * Check if manager is initialized
   */
  get isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Initialize the OPFS manager
   */
  initialize = async (): Promise<void> => {
    // Early return if already initialized
    if (this.initialized) return;

    // Check support with typed error
    if (!OpfsManager.isSupported()) {
      throw createOpfsNotSupportedError();
    }

    try {
      const root = await getOpfsRootDirectory();
      this.rootHandle = await root.getDirectoryHandle(this.config.rootDir, {
        create: true,
      });
      this.initialized = true;
      this.log('Initialized with root:', this.config.rootDir);
    } catch (error) {
      throw createOpfsInitFailedError(getErrorMessage(error));
    }
  };

  /**
   * Ensure manager is initialized
   * Fixed: No non-null assertion, explicit null check
   */
  private ensureInitialized = async (): Promise<FileSystemDirectoryHandle> => {
    if (!this.initialized || !this.rootHandle) {
      await this.initialize();
    }

    // Explicit null check instead of assertion
    if (!this.rootHandle) {
      throw createOpfsInitFailedError('Root handle is null after initialization');
    }

    return this.rootHandle;
  };

  /**
   * Get or create a subdirectory
   */
  private getDirectory = async (
    path: string,
    options: { create?: boolean } = {},
  ): Promise<FileSystemDirectoryHandle> => {
    const root = await this.ensureInitialized();
    const shouldCreate = options.create ?? true;

    if (!path) {
      return root;
    }

    if (shouldCreate) {
      return createDirectoryPath(root, path);
    }

    const existingDirectory = await getDirectoryAtPath(root, path, { create: false });
    if (!existingDirectory) {
      throw new DOMException(`Directory not found: ${path}`, 'NotFoundError');
    }

    return existingDirectory;
  };

  /**
   * Parse a file path into directory path and file name
   * Validates that path is not empty and contains a filename
   */
  private parsePath = (path: string): { dirPath: string; fileName: string } => {
    if (!path || path.trim() === '') {
      throw createValidationError('path', 'Path cannot be empty');
    }

    const pathParts = path.split('/').filter(Boolean);
    if (pathParts.length === 0) {
      throw createValidationError('path', 'Path must contain a filename');
    }

    const fileName = pathParts.pop();
    if (!fileName) {
      throw createValidationError('path', 'Path must contain a filename');
    }
    const dirPath = pathParts.join('/');

    return { dirPath, fileName };
  };

  /**
   * Write a file to OPFS
   * Includes quota handling
   */
  writeFile = async (
    path: string,
    data: ArrayBuffer | Uint8Array | string,
    options: WriteFileOptions,
  ): Promise<OpfsMetadataEntry> => {
    const root = await this.ensureInitialized();

    // Parse and validate path
    const { dirPath, fileName } = this.parsePath(path);

    // Get directory handle
    const dirHandle = dirPath ? await this.getDirectory(dirPath, { create: true }) : root;

    // Create file
    const fileHandle = await dirHandle.getFileHandle(fileName, { create: true });
    const writable = await fileHandle.createWritable();

    // Convert data to Uint8Array for consistent handling and size calculation
    let bytes: Uint8Array;
    if (typeof data === 'string') {
      bytes = new TextEncoder().encode(data);
    } else if (data instanceof ArrayBuffer) {
      bytes = new Uint8Array(data);
    } else {
      bytes = data;
    }

    // Create a fresh ArrayBuffer copy to ensure it's not a SharedArrayBuffer
    const buffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(buffer).set(bytes);

    // Write with quota handling
    try {
      // Create Blob from ArrayBuffer for proper type safety with FileSystemWriteChunkType
      await writable.write(new Blob([buffer]));
      await writable.close();
    } catch (error) {
      // Close writable on error, log any close errors
      try {
        await writable.close();
      } catch (closeError) {
        // Log close error instead of silently ignoring
        this.handleNonFatalError(closeError, 'writeFile.close');
      }

      // Handle quota exceeded
      if (isQuotaExceededError(error)) {
        throw createQuotaExceededError(buffer.byteLength);
      }
      throw error;
    }

    // Create and store metadata
    const metadata = createOpfsMetadata(path, {
      ...options,
      sizeBytes: buffer.byteLength,
    });

    await this.metadataService.set(metadata);
    this.log('Wrote file:', path, metadata);

    return metadata;
  };

  /**
   * Read a file from OPFS
   */
  readFile = async (path: string): Promise<ArrayBuffer> => {
    const root = await this.ensureInitialized();

    // Parse and validate path
    const { dirPath, fileName } = this.parsePath(path);

    const dirHandle = dirPath ? await this.getDirectory(dirPath, { create: false }) : root;

    const fileHandle = await dirHandle.getFileHandle(fileName);
    const file = await fileHandle.getFile();
    return file.arrayBuffer();
  };

  /**
   * Read a file as text
   */
  readFileAsText = async (path: string): Promise<string> => {
    const buffer = await this.readFile(path);
    return new TextDecoder().decode(buffer);
  };

  /**
   * Check if a file exists
   */
  exists = async (path: string): Promise<boolean> => {
    try {
      const root = await this.ensureInitialized();

      // Parse and validate path
      const { dirPath, fileName } = this.parsePath(path);

      const dirHandle = dirPath ? await getDirectoryAtPath(root, dirPath, { create: false }) : root;
      if (!dirHandle) {
        return false;
      }

      return fileExistsInOpfs(dirHandle, fileName);
    } catch (error) {
      // NotFoundError is expected when file doesn't exist
      if (error instanceof DOMException && error.name === 'NotFoundError') {
        return false;
      }
      // Log unexpected errors but still return false
      this.handleNonFatalError(error, 'exists');
      return false;
    }
  };

  /**
   * Delete a file
   */
  deleteFile = async (path: string): Promise<void> => {
    const root = await this.ensureInitialized();

    // Parse and validate path
    const { dirPath, fileName } = this.parsePath(path);

    const dirHandle = dirPath ? await this.getDirectory(dirPath, { create: false }) : root;

    await dirHandle.removeEntry(fileName);
    await this.metadataService.delete(path);

    this.log('Deleted file:', path);
  };

  /**
   * Get file metadata from database
   */
  getMetadata = async (path: string): Promise<OpfsMetadataEntry | undefined> => {
    return this.metadataService.get(path);
  };

  /**
   * Get all files for a table
   */
  getFilesByTable = async (tableName: string): Promise<OpfsMetadataEntry[]> => {
    return this.metadataService.getByTable(tableName);
  };

  /**
   * Get all registered files in dependency order
   */
  getRegisteredFilesInOrder = async (): Promise<OpfsMetadataEntry[]> => {
    return this.metadataService.getInDependencyOrder();
  };

  /**
   * Get all view definitions
   */
  getViewDefinitions = async (): Promise<OpfsMetadataEntry[]> => {
    return this.metadataService.getViews();
  };

  /**
   * Mark file as registered in DuckDB
   */
  markRegistered = async (path: string): Promise<void> => {
    await this.metadataService.markRegistered(path);
    this.log('Marked registered:', path);
  };

  /**
   * Mark file as unregistered from DuckDB
   */
  markUnregistered = async (path: string): Promise<void> => {
    await this.metadataService.markUnregistered(path);
    this.log('Marked unregistered:', path);
  };

  /**
   * Mark all files as unregistered (e.g., after DuckDB restart)
   */
  markAllUnregistered = async (): Promise<void> => {
    await this.metadataService.markAllUnregistered();
    this.log('Marked all files unregistered');
  };

  /**
   * Get total size of all files
   * Optimized: uses each() to avoid loading all records into memory
   */
  getTotalSize = async (): Promise<number> => {
    return this.metadataService.getTotalSize();
  };

  /**
   * List all files in a directory
   */
  listDirectory = async (dirPath?: string): Promise<string[]> => {
    const root = await this.ensureInitialized();
    const dirHandle = dirPath ? await this.getDirectory(dirPath, { create: false }) : root;

    const entries = await listDirectoryEntries(dirHandle);
    return entries.map(([name]) => (dirPath ? `${dirPath}/${name}` : name));
  };

  /**
   * Clear all files and metadata
   */
  clear = async (): Promise<void> => {
    const root = await this.ensureInitialized();
    await clearDirectory(root);

    // Clear metadata
    await this.metadataService.clear();

    this.log('Cleared all files');
  };

  /**
   * Dispose the manager (release resources)
   */
  dispose = async (): Promise<void> => {
    this.rootHandle = null;
    this.initialized = false;
    this.log('Disposed');
  };
}

// =============================================================================
// Singleton Management using createSingletonFactory
// =============================================================================

/**
 * Singleton factory for OpfsManager
 */
const opfsManagerFactory = createSingletonFactory(
  (config: OpfsManagerConfig | undefined) => new OpfsManager(config),
  {
    name: 'OpfsManager',
    compareConfig: createDeepEqualComparison(isEqual, 'OpfsManager'),
    onDispose: async (instance) => {
      if (instance instanceof OpfsManager) {
        await instance.dispose();
      }
    },
  },
);

/**
 * Get or create OPFS manager instance
 */
export const getOpfsManager = (config?: OpfsManagerConfig): OpfsManager => {
  return opfsManagerFactory.getInstance(config);
};

/**
 * Reset OPFS manager instance
 */
export const resetOpfsManager = async (): Promise<void> => {
  await opfsManagerFactory.reset();
};

/**
 * Check if OPFS manager instance exists
 */
export const hasOpfsManager = (): boolean => {
  return opfsManagerFactory.hasInstance();
};
