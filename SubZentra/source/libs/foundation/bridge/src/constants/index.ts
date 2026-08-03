/**
 * Constants for the bridge library
 *
 * Configuration defaults, limits, and SQL constants.
 * For error codes, use FoundationErrorCode from '@open-zentra/foundation-data-model'.
 *
 * @module constants
 */

import { Milliseconds } from '@open-zentra/foundation-data-model';

// =============================================================================
// Default Configuration Values
// =============================================================================

/**
 * Default configuration values for pool and router
 */
export const DEFAULTS = {
  /**
   * Default number of workers (based on hardware concurrency, capped at 8)
   */
  WORKER_COUNT:
    typeof navigator !== 'undefined' ? Math.min(navigator.hardwareConcurrency || 2, 8) : 2,

  /**
   * Maximum queries per worker queue before overflow
   */
  MAX_QUEUE_PER_WORKER: 10,

  /**
   * Default query timeout (30 seconds)
   */
  QUERY_TIMEOUT_MS: Milliseconds.from(30_000),

  /**
   * Worker initialization timeout (10 seconds)
   */
  WORKER_INIT_TIMEOUT_MS: Milliseconds.from(10_000),

  /**
   * Router idle timeout before shutdown (30 seconds)
   */
  IDLE_TIMEOUT_MS: Milliseconds.from(30_000),

  /**
   * OPFS root directory for analytics data
   */
  OPFS_ROOT_DIR: 'open-zentra/analytics',

  /**
   * Maximum SQL identifier length (DuckDB limit)
   */
  MAX_IDENTIFIER_LENGTH: 256,

  /**
   * Maximum retries for worker restart
   */
  MAX_WORKER_RESTART_ATTEMPTS: 3,

  /**
   * Delay between worker restart attempts (ms)
   */
  WORKER_RESTART_DELAY_MS: Milliseconds.from(1000),
} as const;

// =============================================================================
// Priority (constants: CAPITAL_SNAKE_CASE; type: PascalCase)
// =============================================================================

/**
 * Query priority levels
 * - HIGH: Executed before normal/low priority queries
 * - NORMAL: Default priority
 * - LOW: Executed after high/normal priority queries
 */
export const PRIORITY = {
  HIGH: 'high',
  NORMAL: 'normal',
  LOW: 'low',
} as const;

/** Priority level type (PascalCase for types) */
export type PriorityLevel = (typeof PRIORITY)[keyof typeof PRIORITY];

/**
 * Priority numeric values for queue ordering (higher = more urgent)
 */
export const PRIORITY_VALUES: Record<PriorityLevel, number> = {
  [PRIORITY.HIGH]: 3,
  [PRIORITY.NORMAL]: 2,
  [PRIORITY.LOW]: 1,
} as const;

// =============================================================================
// Query Mode (constants: CAPITAL_SNAKE_CASE; type: PascalCase)
// =============================================================================

/**
 * Query lock mode for table access coordination
 * - READ: Allows concurrent access with other readers
 * - WRITE: Exclusive access, blocks all other readers and writers
 */
export const QUERY_MODE = {
  READ: 'read',
  WRITE: 'write',
} as const;

/** Query lock mode type (PascalCase for types) */
export type QueryLockMode = (typeof QUERY_MODE)[keyof typeof QUERY_MODE];

// =============================================================================
// Bridge Type (constants: CAPITAL_SNAKE_CASE; type: PascalCase)
// =============================================================================

/**
 * DuckDB bridge implementation type
 * - WASM: Browser-based DuckDB-WASM implementation
 * - NATIVE: Native DuckDB via Electron IPC
 */
export const BRIDGE_TYPE = {
  WASM: 'wasm',
  NATIVE: 'native',
} as const;

/** Bridge type kind (PascalCase for types) */
export type BridgeType = (typeof BRIDGE_TYPE)[keyof typeof BRIDGE_TYPE];

// =============================================================================
// SQL Constants
// =============================================================================

/**
 * SQL-related constants
 */
export const SQL = {
  /**
   * Valid SQL identifier pattern
   */
  IDENTIFIER_PATTERN: /^[a-zA-Z_][a-zA-Z0-9_]*$/,

  /**
   * Maximum identifier length
   */
  MAX_IDENTIFIER_LENGTH: 256,

  /**
   * SQL reserved words that cannot be used as identifiers
   */
  RESERVED_WORDS: [
    'SELECT',
    'INSERT',
    'UPDATE',
    'DELETE',
    'DROP',
    'CREATE',
    'ALTER',
    'TRUNCATE',
    'TABLE',
    'VIEW',
    'INDEX',
    'FROM',
    'WHERE',
    'AND',
    'OR',
    'NOT',
    'NULL',
    'TRUE',
    'FALSE',
    'AS',
    'ON',
    'JOIN',
    'LEFT',
    'RIGHT',
    'INNER',
    'OUTER',
    'GROUP',
    'BY',
    'ORDER',
    'HAVING',
    'LIMIT',
    'OFFSET',
    'UNION',
    'ALL',
    'DISTINCT',
    'INTO',
    'VALUES',
    'SET',
    'BEGIN',
    'COMMIT',
    'ROLLBACK',
  ] as const,
} as const;

/**
 * SQL reserved word type (derived from SQL.RESERVED_WORDS array)
 */
export type SqlReservedWord = (typeof SQL.RESERVED_WORDS)[number];

// =============================================================================
// Worker Message Types
// =============================================================================

/**
 * DuckDB worker message types for internal communication
 */
export const WORKER_MESSAGE_TYPES = {
  INIT: 'init',
  QUERY: 'query',
  EXECUTE: 'execute',
  REGISTER_FILE: 'register-file',
  UNREGISTER_FILE: 'unregister-file',
  CREATE_VIEW: 'create-view',
  DROP_VIEW: 'drop-view',
  GET_TABLES: 'get-tables',
  GET_VIEWS: 'get-views',
  EXISTS: 'exists',
  SHUTDOWN: 'shutdown',
  EXPORT_PARQUET: 'export-parquet',
  IMPORT_PARQUET: 'import-parquet',
} as const;

/**
 * Worker message type
 */
export type WorkerMessageType = (typeof WORKER_MESSAGE_TYPES)[keyof typeof WORKER_MESSAGE_TYPES];

// =============================================================================
// Runtime Environment (constants: CAPITAL_SNAKE_CASE; type: PascalCase)
// =============================================================================

/**
 * Runtime environment types
 * - ELECTRON: Running in Electron renderer process
 * - WEB: Running in a web browser
 * - NODE: Running in Node.js (non-Electron)
 */
export const RUNTIME_ENVIRONMENT = {
  ELECTRON: 'electron',
  WEB: 'web',
  NODE: 'node',
} as const;

/** Runtime environment kind (PascalCase for types) */
export type RuntimeEnvironmentKind = (typeof RUNTIME_ENVIRONMENT)[keyof typeof RUNTIME_ENVIRONMENT];

// =============================================================================
// Storage Strategy (constants: CAPITAL_SNAKE_CASE; type: PascalCase)
// =============================================================================

/**
 * Storage strategy types for data persistence
 * - OPFS: Origin Private File System (preferred, best performance)
 * - INDEXEDDB: IndexedDB fallback (when OPFS not available)
 * - MEMORY: In-memory storage (fallback when no persistence available)
 */
export const STORAGE_STRATEGY = {
  OPFS: 'opfs',
  INDEXEDDB: 'indexeddb',
  MEMORY: 'memory',
} as const;

/** Storage strategy kind (PascalCase for types) */
export type StorageStrategyKind = (typeof STORAGE_STRATEGY)[keyof typeof STORAGE_STRATEGY];
