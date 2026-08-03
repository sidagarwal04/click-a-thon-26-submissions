/**
 * DuckDB Bridge interface types
 *
 * Defines the unified API for WASM and Native DuckDB implementations.
 *
 * @module types/bridge
 */

import type {
  Milliseconds,
  SqlIdentifier,
  Timestamp,
} from '@open-zentra/foundation-data-model';

import type { BridgeType } from '../constants';

// =============================================================================
// Query Types
// =============================================================================

/**
 * Query options for DuckDB operations
 */
export interface QueryOptions {
  /** Parameterized query values */
  readonly params?: readonly unknown[];
  /** Query timeout in milliseconds */
  readonly timeout?: Milliseconds;
  /** Maximum rows to return */
  readonly limit?: number;
  /** Offset for pagination */
  readonly offset?: number;
  /**
   * AbortSignal for cancellation support
   *
   * Note: DuckDB-WASM queries cannot be interrupted mid-execution.
   * The signal is checked before starting and after completion.
   * If aborted during execution, the result is discarded and an error is thrown.
   */
  readonly signal?: AbortSignal;
}

/**
 * Query result from DuckDB
 */
export interface QueryResult<T extends Record<string, unknown> = Record<string, unknown>> {
  /** Result rows */
  readonly rows: T[];
  /** Column names */
  readonly columns: string[];
  /** Column types */
  readonly types: string[];
  /** Number of rows affected (for mutations) */
  readonly rowsAffected?: number;
  /** Query execution time in milliseconds */
  readonly executionTimeMs: number;
}

// =============================================================================
// View and Table Types
// =============================================================================

/**
 * View definition for creating/tracking views
 */
export interface ViewDefinition {
  /** View name (must be valid SQL identifier) */
  readonly name: SqlIdentifier;
  /** SQL SELECT statement */
  readonly sql: string;
  /** Tables this view depends on */
  readonly dependencies: readonly SqlIdentifier[];
  /** Creation timestamp */
  readonly createdAt: Timestamp;
}

/**
 * Table column information
 */
export interface ColumnInfo {
  /** Column name */
  readonly name: string;
  /** Column data type */
  readonly type: string;
  /** Whether column allows NULL values */
  readonly nullable: boolean;
}

/**
 * Table information
 */
export interface TableInfo {
  /** Table name */
  readonly name: string;
  /** Column definitions */
  readonly columns: readonly ColumnInfo[];
  /** Row count */
  readonly rowCount: number;
  /** Size in bytes (if known) */
  readonly sizeBytes?: number;
}

// =============================================================================
// Bridge Status
// =============================================================================

/**
 * DuckDB bridge status
 */
export interface DuckDBBridgeStatus {
  /** Is the bridge initialized */
  readonly initialized: boolean;
  /** Is currently executing */
  readonly busy: boolean;
  /** Last activity timestamp */
  readonly lastActivityAt: Timestamp | null;
  /** Error if any */
  readonly lastError?: string;
  /** Bridge type */
  readonly type: BridgeType;
}

// =============================================================================
// Bridge Interface
// =============================================================================

/**
 * DuckDB bridge interface - unified API for WASM and Native implementations
 */
export interface DuckDBBridge {
  // Lifecycle
  /** Initialize the bridge */
  initialize(): Promise<void>;

  /** Check if bridge is ready */
  isInitialized(): boolean;

  /** Shutdown and release resources */
  shutdown(): Promise<void>;

  // Query execution
  /** Execute a query and return results */
  query<T extends Record<string, unknown> = Record<string, unknown>>(
    sql: string,
    options?: QueryOptions,
  ): Promise<QueryResult<T>>;

  /** Execute a statement without results */
  execute(sql: string, options?: QueryOptions): Promise<void>;

  // File management
  /** Register a file for querying */
  registerFile(path: string, alias: string): Promise<void>;

  /** Unregister a file */
  unregisterFile(alias: string): Promise<void>;

  // View management
  /** Create a view */
  createView(view: ViewDefinition): Promise<void>;

  /** Drop a view */
  dropView(name: string): Promise<void>;

  /** List all views */
  getViews(): Promise<readonly ViewDefinition[]>;

  // Table management
  /** List all tables */
  getTables(): Promise<readonly TableInfo[]>;

  /** Check if table/view exists */
  exists(name: string): Promise<boolean>;

  // Parquet operations
  /** Export table to Parquet */
  exportToParquet(tableName: string, path: string): Promise<void>;

  /** Import Parquet file */
  importParquet(path: string, tableName: string): Promise<void>;

  // Transaction support
  /** Begin a transaction */
  beginTransaction(): Promise<void>;

  /** Commit current transaction */
  commit(): Promise<void>;

  /** Rollback current transaction */
  rollback(): Promise<void>;
}
