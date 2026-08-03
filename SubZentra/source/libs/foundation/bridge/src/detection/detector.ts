/**
 * Environment detection for Electron vs Web
 * @module detection/detector
 */

import { RUNTIME_ENVIRONMENT, STORAGE_STRATEGY } from '../constants';
import type { RuntimeEnvironmentKind, StorageStrategyKind } from '../constants';

// =============================================================================
// Types
// =============================================================================

/**
 * Environment capabilities
 */
export interface EnvironmentCapabilities {
  /** Current runtime environment */
  readonly runtime: RuntimeEnvironmentKind;
  /** Has native DuckDB support (Electron) */
  readonly hasNativeDuckDB: boolean;
  /** Has OPFS support */
  readonly hasOPFS: boolean;
  /** Has Web Worker support */
  readonly hasWebWorker: boolean;
  /** Has IndexedDB support */
  readonly hasIndexedDB: boolean;
  /** Has BroadcastChannel support */
  readonly hasBroadcastChannel: boolean;
  /** Has SharedArrayBuffer support */
  readonly hasSharedArrayBuffer: boolean;
  /** Is secure context (HTTPS or localhost) */
  readonly isSecureContext: boolean;
  /** User agent info */
  readonly userAgent?: string;
  /** Platform info */
  readonly platform?: string;
}

// =============================================================================
// Detection Helper Functions (Arrow Functions)
// =============================================================================

/**
 * Detect Electron environment
 */
const isElectronEnvironment = (): boolean => {
  // Check for Electron-specific globals
  if (typeof window !== 'undefined') {
    // Check window.process.type (Electron renderer)
    if (typeof (window as Window & { process?: { type?: string } }).process?.type === 'string') {
      return true;
    }

    // Check for electron in user agent
    if (navigator?.userAgent?.toLowerCase().includes('electron')) {
      return true;
    }

    // Check for electronAPI exposed via preload
    if ('electronAPI' in window || 'electron' in window) {
      return true;
    }
  }

  // Check for Node.js process with Electron versions
  if (typeof process !== 'undefined' && process.versions && process.versions.electron) {
    return true;
  }

  return false;
};

/**
 * Detect Node.js environment (not Electron)
 */
const isNodeEnvironment = (): boolean =>
  typeof process !== 'undefined' && !!process.versions?.node && !process.versions?.electron;

/**
 * Detect current runtime environment
 */
const detectRuntime = (): RuntimeEnvironmentKind => {
  if (isElectronEnvironment()) return RUNTIME_ENVIRONMENT.ELECTRON;
  if (isNodeEnvironment()) return RUNTIME_ENVIRONMENT.NODE;
  return RUNTIME_ENVIRONMENT.WEB;
};

/**
 * Check for OPFS support
 */
const checkOPFSSupport = (): boolean =>
  typeof navigator !== 'undefined' &&
  'storage' in navigator &&
  'getDirectory' in (navigator.storage || {});

/**
 * Check for Web Worker support
 */
const checkWebWorkerSupport = (): boolean => typeof Worker !== 'undefined';

/**
 * Check for IndexedDB support
 */
const checkIndexedDBSupport = (): boolean => typeof indexedDB !== 'undefined';

/**
 * Check for BroadcastChannel support
 */
const checkBroadcastChannelSupport = (): boolean => typeof BroadcastChannel !== 'undefined';

/**
 * Check for SharedArrayBuffer support
 */
const checkSharedArrayBufferSupport = (): boolean => typeof SharedArrayBuffer !== 'undefined';

/**
 * Check if secure context
 */
const checkSecureContext = (): boolean => {
  if (typeof window !== 'undefined') {
    return window.isSecureContext ?? false;
  }
  return true; // Assume secure in Node/Electron
};

// =============================================================================
// Environment Detector Class
// =============================================================================

/**
 * Environment detector class
 *
 * Provides static methods for detecting runtime environment and capabilities.
 * Results are cached for performance.
 */
export class EnvironmentDetector {
  private static cachedCapabilities: EnvironmentCapabilities | null = null;

  /**
   * Detect environment capabilities
   */
  static detect(): EnvironmentCapabilities {
    if (this.cachedCapabilities) {
      return this.cachedCapabilities;
    }

    const runtime = detectRuntime();

    this.cachedCapabilities = {
      runtime,
      hasNativeDuckDB: runtime === RUNTIME_ENVIRONMENT.ELECTRON,
      hasOPFS: checkOPFSSupport(),
      hasWebWorker: checkWebWorkerSupport(),
      hasIndexedDB: checkIndexedDBSupport(),
      hasBroadcastChannel: checkBroadcastChannelSupport(),
      hasSharedArrayBuffer: checkSharedArrayBufferSupport(),
      isSecureContext: checkSecureContext(),
      userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
      platform: typeof navigator !== 'undefined' ? navigator.platform : undefined,
    };

    return this.cachedCapabilities;
  }

  /**
   * Clear cached capabilities (for testing)
   */
  static clearCache(): void {
    this.cachedCapabilities = null;
  }

  /**
   * Check if running in Electron
   */
  static isElectron(): boolean {
    return this.detect().runtime === RUNTIME_ENVIRONMENT.ELECTRON;
  }

  /**
   * Check if running in web browser
   */
  static isWeb(): boolean {
    return this.detect().runtime === RUNTIME_ENVIRONMENT.WEB;
  }

  /**
   * Check if running in Node.js
   */
  static isNode(): boolean {
    return this.detect().runtime === RUNTIME_ENVIRONMENT.NODE;
  }

  /**
   * Check if DuckDB WASM should be used
   */
  static shouldUseWasmDuckDB(): boolean {
    const caps = this.detect();
    return caps.runtime === RUNTIME_ENVIRONMENT.WEB && caps.hasWebWorker;
  }

  /**
   * Check if native DuckDB is available
   */
  static hasNativeDuckDB(): boolean {
    return this.detect().hasNativeDuckDB;
  }

  /**
   * Check if OPFS is available
   */
  static hasOPFSSupport(): boolean {
    return this.detect().hasOPFS;
  }

  /**
   * Get recommended storage strategy
   */
  static getStorageStrategy(): StorageStrategyKind {
    const caps = this.detect();

    if (caps.hasOPFS && caps.isSecureContext) {
      return STORAGE_STRATEGY.OPFS;
    }

    if (caps.hasIndexedDB) {
      return STORAGE_STRATEGY.INDEXEDDB;
    }

    return STORAGE_STRATEGY.MEMORY;
  }
}
