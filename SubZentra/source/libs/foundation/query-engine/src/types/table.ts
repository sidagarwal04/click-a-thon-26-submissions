/**
 * Table Types
 *
 * Table source, load state, and configuration types.
 *
 * NOTE: For ConflictStrategy type, import directly from
 * @open-zentra/foundation-data-model
 *
 * @module types/table
 */

// ConflictStrategy is both a const object (value) and a type in data-model.
// We need the value import for the type guard `isConflictStrategy`.
import {
  type ApiMutationDescriptor,
  type ApiQueryDescriptor,
  CONFLICT_STRATEGY,
  DATA_FRESHNESS,
  WRITE_OPERATIONS,
  type ConflictStrategy,
  type DataFreshnessLevel,
  type WriteOperation,
} from '@open-zentra/foundation-data-model';

// =============================================================================
// TABLE SOURCE
// =============================================================================

/**
 * Source of table data.
 *
 * - `api`: Data from HTTP APIs with realtime updates
 * - `local`: Local file uploaded by user (only in DuckDB)
 */
export const TABLE_SOURCES = {
  API: 'api',
  LOCAL: 'local',
} as const;

export type TableSource = (typeof TABLE_SOURCES)[keyof typeof TABLE_SOURCES];

// =============================================================================
// TABLE LOAD STATE
// =============================================================================

/**
 * Load state for a table in the query engine.
 *
 * - `not_loaded`: Table registered but data not yet loaded
 * - `loading`: Currently downloading/processing data
 * - `loaded`: Data ready for querying
 * - `error`: Failed to load data
 * - `stale`: Data loaded but may be outdated
 */
export const TABLE_LOAD_STATES = {
  NOT_LOADED: 'not_loaded',
  LOADING: 'loading',
  LOADED: 'loaded',
  ERROR: 'error',
  STALE: 'stale',
} as const;

export type TableLoadState = (typeof TABLE_LOAD_STATES)[keyof typeof TABLE_LOAD_STATES];

// =============================================================================
// FILE TYPES
// =============================================================================

/**
 * Supported local file types.
 */
export const TABLE_FILE_TYPES = {
  PARQUET: 'parquet',
  CSV: 'csv',
  JSON: 'json',
} as const;

/**
 * Local file type derived from TABLE_FILE_TYPES.
 */
export type TableFileType = (typeof TABLE_FILE_TYPES)[keyof typeof TABLE_FILE_TYPES];

// =============================================================================
// ANALYTICS FRESHNESS LEVELS
// =============================================================================

/**
 * Analytics freshness levels for **per-table** configuration.
 *
 * Describes the data freshness capability of a table's analytics (DuckDB) path.
 * Does not include `historical` — that is a per-query concern.
 *
 * @see FRESHNESS_REQUIREMENTS in `./query` for per-query freshness requirements
 *      (includes `historical` for queries that accept stale data).
 */
export const ANALYTICS_FRESHNESS_LEVELS = {
  ...DATA_FRESHNESS,
} as const;

// =============================================================================
// API DESCRIPTORS
// =============================================================================

/**
 * HTTP API descriptors for a table.
 * Used for transactional reads and mutations.
 */
export interface TableApiFunctions {
  /** List/query function */
  readonly list?: ApiQueryDescriptor;
  /** Get single item function */
  readonly get?: ApiQueryDescriptor;
  /** Create function */
  readonly create?: ApiMutationDescriptor;
  /** Update function */
  readonly update?: ApiMutationDescriptor;
  /** Delete function */
  readonly delete?: ApiMutationDescriptor;
}

// =============================================================================
// PARQUET FILE INFO
// =============================================================================

/**
 * Information about a Parquet file for a table.
 */
export interface ParquetFileInfo {
  /** Download URL (signed, temporary) */
  readonly url: string;
  /** Filename for local storage */
  readonly filename: string;
  /** File size in bytes */
  readonly size: number;
  /** Path in OPFS after download */
  readonly opfsPath?: string;
  /** Whether file has been downloaded */
  readonly downloaded?: boolean;
  /** Row count in this file (if known) */
  readonly rowCount?: number;
  /** File hash for change detection */
  readonly hash?: string;
}

// =============================================================================
// TABLE CONFIGURATION
// =============================================================================

/**
 * Complete configuration for a table in the query engine.
 *
 * This combines:
 * - Source information (API, local file)
 * - Load state tracking
 * - Parquet file metadata (for DuckDB path)
 * - Schema information
 * - Cache/sync settings
 */
export interface TableConfig {
  /**
   * Table name (unique identifier).
   */
  readonly name: string;

  /**
   * Source of data: 'api' or 'local'.
   */
  readonly source: TableSource;

  /**
   * API descriptors for query and mutation access.
   * Required for API-backed tables that need transactional access.
   */
  readonly api?: TableApiFunctions;

  /**
   * Current load state.
   */
  readonly loadState: TableLoadState;

  /**
   * Error from last load attempt (if any).
   */
  readonly loadError?: Error;

  /**
   * Table schema (column name → SQL type).
   */
  readonly schema?: Readonly<Record<string, string>>;

  /**
   * Total row count (if known).
   */
  readonly rowCount?: number;

  /**
   * Parquet files for this table.
   */
  readonly files?: ReadonlyArray<ParquetFileInfo>;

  /**
   * Base OPFS path for table files.
   */
  readonly opfsPath?: string;

  /**
   * File type for local files.
   */
  readonly fileType?: TableFileType;

  /**
   * Whether this is a user-uploaded file.
   */
  readonly isUserUploaded?: boolean;

  /**
   * When data was loaded into DuckDB (client timestamp).
   */
  readonly loadedAt?: number;

  /**
   * When backend last ingested/updated this table's data.
   * This is the KEY FIELD for stale-while-revalidate.
   * If lastIngestedAt > loadedAt, newer data is available.
   */
  readonly lastIngestedAt?: number;

  /**
   * When this table config was registered.
   */
  readonly registeredAt: number;

  /**
   * Stale time override for this table (ms).
   * If not set, uses provider's defaultStaleTime.
   */
  readonly staleTime?: number;

  /**
   * Whether to auto-refresh when newer data is detected.
   */
  readonly autoRefresh?: boolean;

  /**
   * Conflict resolution strategy for offline mutations.
   */
  readonly conflictStrategy?: ConflictStrategy;

  /**
   * Analytics (DuckDB) configuration.
   */
  readonly analytics?: {
    /** Whether analytics is enabled for this table */
    readonly enabled?: boolean;
    /** Data freshness requirement */
    readonly freshness?: DataFreshnessLevel;
    /** Analytics-specific stale time */
    readonly staleTime?: number;
  };
}

// =============================================================================
// TABLE REGISTRATION OPTIONS
// =============================================================================

/**
 * Options for registering a new table.
 */
export interface RegisterTableOptions {
  /** Table name (unique identifier) */
  readonly name: string;
  /** Source: 'api' or 'local' */
  readonly source: TableSource;
  /** HTTP API descriptors */
  readonly api?: TableApiFunctions;
  /** File type for local files */
  readonly fileType?: TableFileType;
  /** Whether this is a user-uploaded file */
  readonly isUserUploaded?: boolean;
  /** Stale time override (ms) */
  readonly staleTime?: number;
  /** Auto-refresh on update */
  readonly autoRefresh?: boolean;
  /** Conflict resolution strategy */
  readonly conflictStrategy?: ConflictStrategy;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if value is a valid table source.
 */
export const isTableSource = (value: unknown): value is TableSource => {
  return typeof value === 'string' && Object.values(TABLE_SOURCES).includes(value as TableSource);
};

/**
 * Check if value is a valid table load state.
 */
export const isTableLoadState = (value: unknown): value is TableLoadState => {
  return (
    typeof value === 'string' && Object.values(TABLE_LOAD_STATES).includes(value as TableLoadState)
  );
};

/**
 * Check if value is a valid conflict strategy.
 * Uses the canonical ConflictStrategy const from foundation-data-model.
 */
export const isConflictStrategy = (value: unknown): value is ConflictStrategy => {
  return (
    typeof value === 'string' &&
    (Object.values(CONFLICT_STRATEGY) as readonly string[]).includes(value)
  );
};

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Check if a table is loaded and ready for querying.
 */
export const isTableReady = (table: TableConfig): boolean => {
  return (
    table.loadState === TABLE_LOAD_STATES.LOADED || table.loadState === TABLE_LOAD_STATES.STALE
  );
};

/**
 * Check if a table needs to be loaded.
 */
export const tableNeedsLoading = (table: TableConfig): boolean => {
  return table.loadState === TABLE_LOAD_STATES.NOT_LOADED;
};

/**
 * Check if table is currently loading.
 */
export const isTableLoading = (table: TableConfig): boolean => {
  return table.loadState === TABLE_LOAD_STATES.LOADING;
};

/**
 * Check if table has load error.
 */
export const hasTableError = (table: TableConfig): boolean => {
  return table.loadState === TABLE_LOAD_STATES.ERROR;
};

/**
 * Check if table data is stale (may need refresh).
 */
export const isTableStale = (table: TableConfig, defaultStaleTime: number): boolean => {
  if (table.loadState === TABLE_LOAD_STATES.STALE) {
    return true;
  }

  if (!table.loadedAt) {
    return true;
  }

  const staleTime = table.staleTime ?? defaultStaleTime;
  const age = Date.now() - table.loadedAt;
  return age > staleTime;
};

/**
 * Check if newer data is available on the server.
 * Compares lastIngestedAt (server) with loadedAt (client).
 */
export const hasNewerServerData = (table: TableConfig): boolean => {
  if (!table.lastIngestedAt || !table.loadedAt) {
    return false;
  }
  return table.lastIngestedAt > table.loadedAt;
};

/**
 * Check if table can use API path (has list API defined).
 */
export const tableHasListApi = (table: TableConfig): boolean => {
  return !!table.api?.list;
};

/**
 * Check if table can use API for mutations.
 */
export const tableHasMutationApi = (table: TableConfig, operation: WriteOperation): boolean => {
  switch (operation) {
    case WRITE_OPERATIONS.CREATE:
      return !!table.api?.create;
    case WRITE_OPERATIONS.UPDATE:
      return !!table.api?.update;
    case WRITE_OPERATIONS.DELETE:
      return !!table.api?.delete;
    default:
      return false;
  }
};
