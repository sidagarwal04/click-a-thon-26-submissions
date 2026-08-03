/**
 * WASM DuckDB Bridge - Direct DuckDB-WASM Integration
 *
 * This module provides a bridge to DuckDB-WASM using the official Vite integration
 * pattern. It uses AsyncDuckDB directly, eliminating the need for a wrapper worker.
 *
 * @module wasm/wasm-bridge
 */

import type {
  AsyncDuckDB,
  AsyncDuckDBConnection,
  Logger as DuckDBLogger,
} from '@duckdb/duckdb-wasm';

import {
  QueryCancelledError,
  QueryExecutionError,
  QueryId,
  Timestamp,
} from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  getErrorMessage,
  normalizeError,
  type Logger,
} from '@open-zentra/foundation-utils';

import { convertArrowToQueryResult } from '../duckdb/arrow-converter';
import { BridgeInitializationError, BridgeNotInitializedError } from '../errors/bridge-errors';
import type {
  ColumnInfo,
  DuckDBBridge,
  QueryOptions,
  QueryResult,
  TableInfo,
  ViewDefinition,
} from '../types/bridge';
import {
  applyLimitOffset,
  buildCreateViewSql,
  buildDropViewSql,
  escapeString,
  quoteIdentifier,
  validateIdentifier,
} from '../utils/sql';
import { createDuckDBInstance } from './duckdb-init';

// =============================================================================
// Types
// =============================================================================

/**
 * WASM bridge configuration
 */
export interface WasmDuckDBBridgeConfig {
  /** Enable debug logging */
  debug?: boolean;
  /** Custom DuckDB logger */
  duckdbLogger?: DuckDBLogger;
}

// =============================================================================
// WASM Bridge Implementation
// =============================================================================

/**
 * WASM DuckDB Bridge implementation
 *
 * Uses AsyncDuckDB directly from @duckdb/duckdb-wasm with proper Vite bundling.
 * This eliminates the wrapper worker anti-pattern and provides direct access
 * to DuckDB's async API.
 */
export class WasmDuckDBBridge implements DuckDBBridge {
  private db: AsyncDuckDB | null = null;
  private conn: AsyncDuckDBConnection | null = null;
  private worker: Worker | null = null;
  private initialized = false;
  private inTransaction = false;
  private readonly duckdbLogger?: DuckDBLogger;
  private readonly logger: Logger;

  /** Track view definitions for rehydration support */
  private readonly viewDefinitions = new Map<string, ViewDefinition>();

  constructor(config: WasmDuckDBBridgeConfig = {}) {
    this.duckdbLogger = config.duckdbLogger;
    this.logger = createDebugLogger('WasmDuckDBBridge', config.debug ?? false);
  }

  // ===========================================================================
  // Private Helpers
  // ===========================================================================

  /**
   * Ensure bridge is initialized before operations
   */
  private ensureInitialized(): void {
    if (!this.initialized || !this.conn) {
      throw new BridgeNotInitializedError('WasmDuckDBBridge');
    }
  }

  /**
   * Get a non-null initialized connection.
   */
  private getConnection(): AsyncDuckDBConnection {
    this.ensureInitialized();
    const connection = this.conn;
    if (!connection) {
      throw new BridgeNotInitializedError('WasmDuckDBBridge');
    }
    return connection;
  }

  /**
   * Get a non-null initialized DuckDB instance.
   */
  private getDatabase(): AsyncDuckDB {
    this.ensureInitialized();
    const database = this.db;
    if (!database) {
      throw new BridgeNotInitializedError('WasmDuckDBBridge');
    }
    return database;
  }

  // ===========================================================================
  // Lifecycle Methods
  // ===========================================================================

  /**
   * Initialize the DuckDB-WASM instance
   *
   * This creates the DuckDB instance with proper Vite-bundled WASM assets.
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    this.logger.info('Initializing WASM bridge');

    try {
      const { db, conn, worker } = await createDuckDBInstance(this.duckdbLogger);

      this.db = db;
      this.conn = conn;
      this.worker = worker;
      this.initialized = true;

      this.logger.info('Initialized successfully');
    } catch (error) {
      const err = normalizeError(error);
      this.logger.error('Initialization failed', { error: err.message });
      throw new BridgeInitializationError('WasmDuckDBBridge', err);
    }
  }

  /**
   * Check if the bridge is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * Shutdown the DuckDB instance and release resources
   * Note: View definitions are preserved for rehydration via getViewDefinitions()
   */
  async shutdown(): Promise<void> {
    if (!this.initialized) return;

    this.logger.info('Shutting down');

    try {
      // Rollback any pending transaction
      if (this.inTransaction && this.conn) {
        await this.conn.query('ROLLBACK');
        this.inTransaction = false;
      }

      // Close the connection
      if (this.conn) {
        await this.conn.close();
        this.conn = null;
      }

      // Terminate the database
      if (this.db) {
        await this.db.terminate();
        this.db = null;
      }

      // Terminate the worker
      if (this.worker) {
        this.worker.terminate();
        this.worker = null;
      }
    } catch (error) {
      this.logger.error('Shutdown error', {
        error: getErrorMessage(error),
      });
    }

    this.initialized = false;
    // Note: viewDefinitions are preserved for rehydration
    this.logger.info('Shutdown complete');
  }

  // ===========================================================================
  // Query Execution
  // ===========================================================================

  /**
   * Execute a SQL query and return results
   *
   * @param sql - SQL query string
   * @param options - Query options including signal for cancellation
   * @returns Query result with rows, columns, and types
   * @throws QueryCancelledError if the signal is aborted
   * @throws QueryExecutionError if the query fails
   */
  async query<T extends Record<string, unknown> = Record<string, unknown>>(
    sql: string,
    options?: QueryOptions,
  ): Promise<QueryResult<T>> {
    const conn = this.getConnection();

    // Generate a query ID for logging/tracking
    const queryId = QueryId.create();

    // Check if already aborted before starting
    if (options?.signal?.aborted) {
      this.logger.debug('Query aborted before start', { queryId });
      throw new QueryCancelledError(queryId, 'user');
    }

    // Apply LIMIT and OFFSET if provided and not already in SQL
    let finalSql = sql;
    if (options?.limit !== undefined || options?.offset !== undefined) {
      finalSql = applyLimitOffset(sql, options.limit, options.offset);
    }

    this.logger.debug('Executing query', { queryId, sqlPreview: finalSql.slice(0, 100) });

    try {
      const startTime = performance.now();

      // Use prepared statement if params provided
      let result;
      if (options?.params && options.params.length > 0) {
        const stmt = await conn.prepare(finalSql);
        result = await stmt.query(...options.params);
        await stmt.close();
      } else {
        result = await conn.query(finalSql);
      }

      // Check if aborted during execution
      // Note: We can't cancel the actual DuckDB query mid-execution,
      // but we can discard the result and throw an error
      if (options?.signal?.aborted) {
        this.logger.debug('Query aborted after execution', { queryId });
        throw new QueryCancelledError(queryId, 'user');
      }

      const executionTimeMs = performance.now() - startTime;

      this.logger.debug('Query completed', {
        queryId,
        executionTimeMs: executionTimeMs.toFixed(2),
        rowCount: result.numRows,
      });

      return convertArrowToQueryResult<T>(result, executionTimeMs);
    } catch (error) {
      // Re-throw QueryCancelledError as-is
      if (error instanceof QueryCancelledError) {
        throw error;
      }
      const err = normalizeError(error);
      this.logger.error('Query failed', { queryId, error: err.message });
      throw new QueryExecutionError(queryId, finalSql, err);
    }
  }

  /**
   * Execute a SQL statement without returning results
   *
   * @param sql - SQL statement to execute
   * @param options - Query options including signal for cancellation
   * @throws QueryCancelledError if the signal is aborted
   * @throws QueryExecutionError if the statement fails
   */
  async execute(sql: string, options?: QueryOptions): Promise<void> {
    const conn = this.getConnection();

    const queryId = QueryId.create();

    // Check if already aborted before starting
    if (options?.signal?.aborted) {
      this.logger.debug('Statement aborted before start', { queryId });
      throw new QueryCancelledError(queryId, 'user');
    }

    this.logger.debug('Executing statement', { queryId, sqlPreview: sql.slice(0, 100) });

    try {
      if (options?.params && options.params.length > 0) {
        const stmt = await conn.prepare(sql);
        await stmt.query(...options.params);
        await stmt.close();
      } else {
        await conn.query(sql);
      }

      // Check if aborted during execution
      if (options?.signal?.aborted) {
        this.logger.debug('Statement aborted after execution', { queryId });
        throw new QueryCancelledError(queryId, 'user');
      }
    } catch (error) {
      // Re-throw QueryCancelledError as-is
      if (error instanceof QueryCancelledError) {
        throw error;
      }
      const err = normalizeError(error);
      this.logger.error('Execute failed', { queryId, error: err.message });
      throw new QueryExecutionError(queryId, sql, err);
    }
  }

  // ===========================================================================
  // File Management
  // ===========================================================================

  /**
   * Register a file from OPFS/filesystem
   */
  async registerFile(path: string, alias: string): Promise<void> {
    const db = this.getDatabase();

    // Validate alias as identifier
    const safeAlias = validateIdentifier(alias);

    this.logger.debug('Registering file', { path, alias: safeAlias });

    // DuckDB protocol for OPFS: 2 = BROWSER_FILEREADER
    await db.registerFileHandle(safeAlias, path, 2, true);
  }

  /**
   * Unregister a file
   */
  async unregisterFile(alias: string): Promise<void> {
    const db = this.getDatabase();

    const safeAlias = validateIdentifier(alias);

    this.logger.debug('Unregistering file', { alias: safeAlias });

    await db.dropFile(safeAlias);
  }

  // ===========================================================================
  // View Management
  // ===========================================================================

  /**
   * Create a view and track its definition for rehydration
   */
  async createView(view: ViewDefinition): Promise<void> {
    const conn = this.getConnection();

    // Validate view name
    const safeName = validateIdentifier(view.name);

    this.logger.debug('Creating view', { name: safeName });

    // Build safe SQL using utilities
    const createSql = buildCreateViewSql(safeName, view.sql, true);
    await conn.query(createSql);

    // Track the view definition for getViews() and rehydration
    const trackedView: ViewDefinition = {
      ...view,
      name: safeName,
      createdAt: view.createdAt ?? Timestamp.now(),
    };
    this.viewDefinitions.set(safeName, trackedView);
  }

  /**
   * Drop a view and remove from tracking
   */
  async dropView(name: string): Promise<void> {
    const conn = this.getConnection();

    const safeName = validateIdentifier(name);

    this.logger.debug('Dropping view', { name: safeName });

    const dropSql = buildDropViewSql(safeName, true);
    await conn.query(dropSql);

    // Remove from tracked definitions
    this.viewDefinitions.delete(safeName);
  }

  /**
   * Get list of views with their full definitions
   * Returns tracked view definitions which include the SQL and dependencies
   * needed for rehydration after shutdown.
   */
  async getViews(): Promise<readonly ViewDefinition[]> {
    const conn = this.getConnection();

    // Query for view names to ensure we have current state
    const result = await conn.query(
      "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'",
    );

    const viewNames = new Set(result.toArray().map((row) => String(row.table_name)));

    // Return tracked definitions for views that still exist
    const views: ViewDefinition[] = [];
    for (const [name, definition] of this.viewDefinitions) {
      if (viewNames.has(name)) {
        views.push(definition);
      } else {
        // View was dropped externally, remove from tracking
        this.viewDefinitions.delete(name);
      }
    }

    // Also add any views that exist but weren't tracked
    for (const viewName of viewNames) {
      if (!this.viewDefinitions.has(viewName)) {
        views.push({
          name: validateIdentifier(viewName),
          sql: '', // Unknown - created externally
          dependencies: [],
          createdAt: Timestamp.now(),
        });
      }
    }

    return views;
  }

  // ===========================================================================
  // Table Management
  // ===========================================================================

  /**
   * Get list of tables with column info
   */
  async getTables(): Promise<readonly TableInfo[]> {
    const conn = this.getConnection();

    // Get table names
    const tablesResult = await conn.query(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'",
    );

    const tables: TableInfo[] = [];

    // Prepare statement for column queries (parameterized for safety)
    const columnStmt = await conn.prepare(
      "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = ? AND table_schema = 'main'",
    );

    try {
      for (const row of tablesResult.toArray()) {
        const tableName = String(row.table_name);

        // Get column info using prepared statement
        const columnsResult = await columnStmt.query(tableName);

        const columns: ColumnInfo[] = columnsResult.toArray().map((col) => ({
          name: String(col.column_name),
          type: String(col.data_type),
          nullable: col.is_nullable === 'YES',
        }));

        // Get row count - table name is from database, quote for safety
        const safeTableName = validateIdentifier(tableName);
        const countResult = await conn.query(
          `SELECT COUNT(*) as cnt FROM ${quoteIdentifier(safeTableName)}`,
        );
        const rowCount = Number(countResult.toArray()[0]?.cnt ?? 0);

        tables.push({
          name: tableName,
          columns,
          rowCount,
        });
      }
    } finally {
      await columnStmt.close();
    }

    return tables;
  }

  /**
   * Check if a table/view exists
   */
  async exists(name: string): Promise<boolean> {
    const conn = this.getConnection();

    // Use prepared statement for safety against SQL injection
    const stmt = await conn.prepare(
      "SELECT COUNT(*) as cnt FROM information_schema.tables WHERE table_name = ? AND table_schema = 'main'",
    );

    try {
      const result = await stmt.query(name);
      const rows = result.toArray();
      return rows.length > 0 && Number(rows[0].cnt) > 0;
    } finally {
      await stmt.close();
    }
  }

  // ===========================================================================
  // Parquet Operations
  // ===========================================================================

  /**
   * Export a table to Parquet format
   *
   * @note DuckDB does not support parameterized file paths in COPY commands.
   * The path is escaped using escapeString. Callers should ensure paths come
   * from trusted sources (e.g., internal OPFS paths, not user input).
   */
  async exportToParquet(tableName: string, path: string): Promise<void> {
    const conn = this.getConnection();

    const safeTableName = validateIdentifier(tableName);
    // DuckDB COPY doesn't support parameterized paths - escape for string literal
    // SECURITY: Paths should come from trusted internal sources only
    const safePath = escapeString(path);

    this.logger.debug('Exporting to Parquet', { table: safeTableName, path });

    await conn.query(`COPY ${quoteIdentifier(safeTableName)} TO '${safePath}' (FORMAT PARQUET)`);
  }

  /**
   * Import a Parquet file into a table
   *
   * @note DuckDB does not support parameterized file paths in read_parquet.
   * The path is escaped using escapeString. Callers should ensure paths come
   * from trusted sources (e.g., internal OPFS paths, not user input).
   */
  async importParquet(path: string, tableName: string): Promise<void> {
    const conn = this.getConnection();

    const safeTableName = validateIdentifier(tableName);
    // DuckDB read_parquet doesn't support parameterized paths - escape for string literal
    // SECURITY: Paths should come from trusted internal sources only
    const safePath = escapeString(path);

    this.logger.debug('Importing Parquet', { path, table: safeTableName });

    await conn.query(
      `CREATE TABLE ${quoteIdentifier(safeTableName)} AS SELECT * FROM read_parquet('${safePath}')`,
    );
  }

  // ===========================================================================
  // Transaction Support
  // ===========================================================================

  /**
   * Begin a transaction
   */
  async beginTransaction(): Promise<void> {
    const conn = this.getConnection();

    if (this.inTransaction) {
      this.logger.warn('Transaction already in progress');
      return;
    }

    this.logger.debug('Beginning transaction');
    await conn.query('BEGIN TRANSACTION');
    this.inTransaction = true;
  }

  /**
   * Commit current transaction
   */
  async commit(): Promise<void> {
    const conn = this.getConnection();

    if (!this.inTransaction) {
      this.logger.warn('No transaction to commit');
      return;
    }

    this.logger.debug('Committing transaction');
    await conn.query('COMMIT');
    this.inTransaction = false;
  }

  /**
   * Rollback current transaction
   */
  async rollback(): Promise<void> {
    const conn = this.getConnection();

    if (!this.inTransaction) {
      this.logger.warn('No transaction to rollback');
      return;
    }

    this.logger.debug('Rolling back transaction');
    await conn.query('ROLLBACK');
    this.inTransaction = false;
  }

  // ===========================================================================
  // Rehydration Support
  // ===========================================================================

  /**
   * Get all tracked view definitions for rehydration
   * Call this before shutdown to save view definitions for later restoration
   */
  getViewDefinitions(): ViewDefinition[] {
    return Array.from(this.viewDefinitions.values());
  }

  /**
   * Clear view definition tracking (e.g., after full rehydration)
   */
  clearViewDefinitions(): void {
    this.viewDefinitions.clear();
  }
}
