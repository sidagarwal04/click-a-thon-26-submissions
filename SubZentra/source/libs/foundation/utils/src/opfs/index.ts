/**
 * OPFS (Origin Private File System) utilities
 *
 * Shared utilities for working with the Origin Private File System API.
 * Provides type augmentation, support detection, and common helpers.
 *
 * @module opfs
 */

// =============================================================================
// Type Augmentation for FileSystemDirectoryHandle
// =============================================================================

/**
 * Augment FileSystemDirectoryHandle to support async iteration.
 * This is needed because TypeScript's lib.dom.d.ts may not include
 * the async iterator definition for FileSystemDirectoryHandle.
 */
declare global {
  interface FileSystemDirectoryHandle {
    entries(): AsyncIterableIterator<[string, FileSystemHandle]>;
    keys(): AsyncIterableIterator<string>;
    values(): AsyncIterableIterator<FileSystemHandle>;
    [Symbol.asyncIterator](): AsyncIterableIterator<[string, FileSystemHandle]>;
  }
}

// =============================================================================
// Support Detection
// =============================================================================

/**
 * Check if OPFS is supported in the current environment
 *
 * OPFS requires:
 * - navigator object (browser environment)
 * - navigator.storage (Storage API)
 * - navigator.storage.getDirectory (OPFS API)
 *
 * @returns true if OPFS is supported
 *
 * @example
 * ```typescript
 * if (isOpfsSupported()) {
 *   const root = await getOpfsRootDirectory();
 *   // ... work with OPFS
 * } else {
 *   console.warn('OPFS not supported, falling back to IndexedDB');
 * }
 * ```
 */
export const isOpfsSupported = (): boolean => {
  if (typeof navigator === 'undefined') return false;
  if (!('storage' in navigator)) return false;
  if (!('getDirectory' in (navigator.storage || {}))) return false;
  return true;
};

// =============================================================================
// Root Directory Access
// =============================================================================

/**
 * Get the OPFS root directory handle
 *
 * @returns The root FileSystemDirectoryHandle
 * @throws Error if OPFS is not supported
 *
 * @example
 * ```typescript
 * const root = await getOpfsRootDirectory();
 * const myDir = await root.getDirectoryHandle('my-app', { create: true });
 * ```
 */
export const getOpfsRootDirectory = async (): Promise<FileSystemDirectoryHandle> => {
  if (!isOpfsSupported()) {
    throw new Error('OPFS is not supported in this environment');
  }
  return navigator.storage.getDirectory();
};

// =============================================================================
// Directory Utilities
// =============================================================================

/**
 * Create a directory path in OPFS, creating intermediate directories as needed
 *
 * @param root - The root directory handle
 * @param path - Path to create (e.g., 'data/analytics/cache')
 * @returns The final directory handle
 *
 * @example
 * ```typescript
 * const root = await getOpfsRootDirectory();
 * const cacheDir = await createDirectoryPath(root, 'my-app/data/cache');
 * ```
 */
export const createDirectoryPath = async (
  root: FileSystemDirectoryHandle,
  path: string,
): Promise<FileSystemDirectoryHandle> => {
  const parts = path.split('/').filter(Boolean);
  let current = root;

  for (const part of parts) {
    current = await current.getDirectoryHandle(part, { create: true });
  }

  return current;
};

/**
 * Get a directory handle at a path, optionally creating it
 *
 * @param root - The root directory handle
 * @param path - Path to the directory (e.g., 'data/analytics')
 * @param options - Options for getting the directory
 * @returns The directory handle, or null if not found and create is false
 *
 * @example
 * ```typescript
 * const dir = await getDirectoryAtPath(root, 'my-app/data', { create: false });
 * if (dir) {
 *   // Directory exists
 * }
 * ```
 */
export const getDirectoryAtPath = async (
  root: FileSystemDirectoryHandle,
  path: string,
  options: { create?: boolean } = {},
): Promise<FileSystemDirectoryHandle | null> => {
  const parts = path.split('/').filter(Boolean);
  let current = root;

  try {
    for (const part of parts) {
      current = await current.getDirectoryHandle(part, { create: options.create });
    }
    return current;
  } catch (error) {
    if ((error as DOMException).name === 'NotFoundError' && !options.create) {
      return null;
    }
    throw error;
  }
};

// =============================================================================
// File Utilities
// =============================================================================

/**
 * Check if a file exists in OPFS
 *
 * @param directory - The directory to check in
 * @param fileName - Name of the file
 * @returns true if the file exists
 *
 * @example
 * ```typescript
 * const exists = await fileExistsInOpfs(dataDir, 'config.json');
 * ```
 */
export const fileExistsInOpfs = async (
  directory: FileSystemDirectoryHandle,
  fileName: string,
): Promise<boolean> => {
  try {
    await directory.getFileHandle(fileName);
    return true;
  } catch {
    return false;
  }
};

/**
 * List all entries in a directory
 *
 * @param directory - The directory to list
 * @returns Array of [name, handle] tuples
 *
 * @example
 * ```typescript
 * const entries = await listDirectoryEntries(dataDir);
 * for (const [name, handle] of entries) {
 *   console.log(name, handle.kind); // 'file' or 'directory'
 * }
 * ```
 */
export const listDirectoryEntries = async (
  directory: FileSystemDirectoryHandle,
): Promise<Array<[string, FileSystemHandle]>> => {
  const entries: Array<[string, FileSystemHandle]> = [];
  for await (const entry of directory.entries()) {
    entries.push(entry);
  }
  return entries;
};

/**
 * Recursively delete all contents of a directory
 *
 * @param directory - The directory to clear
 *
 * @example
 * ```typescript
 * await clearDirectory(cacheDir);
 * ```
 */
export const clearDirectory = async (directory: FileSystemDirectoryHandle): Promise<void> => {
  for await (const [name] of directory.entries()) {
    await directory.removeEntry(name, { recursive: true });
  }
};
