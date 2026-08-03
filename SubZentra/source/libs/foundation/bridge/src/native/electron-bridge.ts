/**
 * Electron DuckDB Bridge - Native DuckDB via IPC
 * @module native/electron-bridge
 */

import {
  QueryCancelledError,
  QueryExecutionError,
  QueryId,
} from '@open-zentra/foundation-data-model';
import type { Logger } from '@open-zentra/foundation-utils';
import { createDebugLogger, normalizeError } from '@open-zentra/foundation-utils';

import { BridgeInitializationError, BridgeNotInitializedError } from '../errors/bridge-errors';
import type {
  DuckDBBridge,
  QueryOptions,
  QueryResult,
  TableInfo,
  ViewDefinition,
} from '../types/bridge';
import { validateIdentifier, validateViewSql } from '../utils/sql';

/**
 * Electron API interface (exposed via preload)
 */
interface ElectronDuckDBAPI {
  query<T extends Record<string, unknown>>(
    sql: string,
    params?: readonly unknown[],
  ): Promise<readonly T[]>;
  execute(sql: string, params?: readonly unknown[]): Promise<void>;
  registerFile(path: string, alias: string): Promise<void>;
  unregisterFile(alias: string): Promise<void>;
  createView(name: string, sql: string): Promise<void>;
  dropView(name: string): Promise<void>;
  getTables(): Promise<TableInfo[]>;
  getViews(): Promise<ViewDefinition[]>;
  exists(name: string): Promise<boolean>;
  shutdown(): Promise<void>;
  exportToParquet(tableName: string, path: string): Promise<void>;
  importParquet(path: string, tableName: string): Promise<void>;
}

/**
 * Get Electron DuckDB API from window
 */
const getElectronAPI = (): ElectronDuckDBAPI | null => {
  if (typeof window !== 'undefined' && 'electronDuckDB' in window) {
    return (window as Window & { electronDuckDB: ElectronDuckDBAPI }).electronDuckDB;
  }
  return null;
};

/**
 * Infer a DuckDB-compatible column type from a JavaScript runtime value.
 *
 * This provides best-effort type detection when the native bridge does not
 * expose explicit column metadata.
 */
const inferColumnType = (value: unknown): string => {
  if (value === null || value === undefined) return 'unknown';
  if (typeof value === 'string') return 'VARCHAR';
  if (typeof value === 'number') return Number.isInteger(value) ? 'INTEGER' : 'DOUBLE';
  if (typeof value === 'boolean') return 'BOOLEAN';
  if (typeof value === 'bigint') return 'BIGINT';
  if (value instanceof Date) return 'TIMESTAMP';
  if (Array.isArray(value)) return 'LIST';
  if (typeof value === 'object') return 'STRUCT';
  return 'unknown';
};

/**
 * Electron DuckDB bridge configuration
 */
export interface ElectronDuckDBBridgeConfig {
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Electron DuckDB Bridge implementation
 */
export class ElectronDuckDBBridge implements DuckDBBridge {
  private api: ElectronDuckDBAPI | null = null;
  private initialized = false;
  private inTransaction = false;
  private readonly logger: Logger;

  constructor(config: ElectronDuckDBBridgeConfig = {}) {
    this.logger = createDebugLogger('ElectronDuckDBBridge', config.debug ?? false);
  }

  async initialize(): Promise<void> {
    if (this.initialized) return;

    try {
      this.api = getElectronAPI();

      if (!this.api) {
        throw new Error(
          'Electron DuckDB API not found. Ensure preload script exposes electronDuckDB.',
        );
      }

      this.initialized = true;
      this.logger.info('Initialized');
    } catch (error) {
      throw new BridgeInitializationError('ElectronDuckDBBridge', normalizeError(error));
    }
  }

  isInitialized(): boolean {
    return this.initialized;
  }

  private ensureInitialized(): void {
    if (!this.initialized || !this.api) {
      throw new BridgeNotInitializedError('ElectronDuckDBBridge');
    }
  }

  /**
   * Return the initialized API instance with non-null typing.
   */
  private getApi(): ElectronDuckDBAPI {
    this.ensureInitialized();
    const api = this.api;
    if (!api) {
      throw new BridgeNotInitializedError('ElectronDuckDBBridge');
    }
    return api;
  }

  async query<T extends Record<string, unknown> = Record<string, unknown>>(
    sql: string,
    options?: QueryOptions,
  ): Promise<QueryResult<T>> {
    const api = this.getApi();
    const queryId = QueryId.create();

    if (options?.signal?.aborted) {
      throw new QueryCancelledError(queryId, 'user');
    }

    this.logger.debug('Query', { sqlPreview: sql.slice(0, 80) });

    const startTime = performance.now();

    try {
      const result = await api.query<T & Record<string, unknown>>(sql, options?.params);
      const executionTimeMs = performance.now() - startTime;

      if (options?.signal?.aborted) {
        throw new QueryCancelledError(queryId, 'user');
      }

      const rows = [...result];
      const firstRow = rows[0];
      const columns = firstRow ? Object.keys(firstRow) : [];

      return {
        rows,
        columns,
        types: columns.map((col) => (firstRow ? inferColumnType(firstRow[col]) : 'unknown')),
        executionTimeMs,
      };
    } catch (error) {
      if (error instanceof QueryCancelledError) {
        throw error;
      }
      const normalizedError = normalizeError(error);
      this.logger.error('Query error', {
        error: normalizedError.message,
      });
      throw new QueryExecutionError(queryId, sql, normalizedError);
    }
  }

  async execute(sql: string, options?: QueryOptions): Promise<void> {
    const api = this.getApi();
    const queryId = QueryId.create();

    if (options?.signal?.aborted) {
      throw new QueryCancelledError(queryId, 'user');
    }

    this.logger.debug('Execute', { sqlPreview: sql.slice(0, 80) });

    try {
      await api.execute(sql, options?.params);
      if (options?.signal?.aborted) {
        throw new QueryCancelledError(queryId, 'user');
      }
    } catch (error) {
      if (error instanceof QueryCancelledError) {
        throw error;
      }
      throw new QueryExecutionError(queryId, sql, normalizeError(error));
    }
  }

  async registerFile(path: string, alias: string): Promise<void> {
    const api = this.getApi();
    this.logger.debug('Register file', { path, alias });

    await api.registerFile(path, alias);
  }

  async unregisterFile(alias: string): Promise<void> {
    const api = this.getApi();
    this.logger.debug('Unregister file', { alias });

    await api.unregisterFile(alias);
  }

  async createView(view: ViewDefinition): Promise<void> {
    const api = this.getApi();

    // Validate view name and SQL (matches WASM bridge validation)
    const safeName = validateIdentifier(view.name);
    validateViewSql(view.sql);

    this.logger.debug('Create view', { name: safeName });

    await api.createView(safeName, view.sql);
  }

  async dropView(name: string): Promise<void> {
    const api = this.getApi();
    this.logger.debug('Drop view', { name });

    await api.dropView(name);
  }

  async getTables(): Promise<readonly TableInfo[]> {
    return this.getApi().getTables();
  }

  async getViews(): Promise<readonly ViewDefinition[]> {
    return this.getApi().getViews();
  }

  async exists(name: string): Promise<boolean> {
    return this.getApi().exists(name);
  }

  async shutdown(): Promise<void> {
    if (!this.initialized) return;
    const api = this.getApi();

    // Rollback any pending transaction
    if (this.inTransaction) {
      try {
        await api.execute('ROLLBACK');
      } catch {
        // Ignore errors during cleanup
      }
      this.inTransaction = false;
    }

    this.logger.info('Shutting down');
    await api.shutdown();
    this.initialized = false;
    this.api = null;
  }

  async exportToParquet(tableName: string, path: string): Promise<void> {
    const api = this.getApi();
    this.logger.debug('Export to Parquet', { table: tableName, path });

    await api.exportToParquet(tableName, path);
  }

  async importParquet(path: string, tableName: string): Promise<void> {
    const api = this.getApi();
    this.logger.debug('Import Parquet', { path, table: tableName });

    await api.importParquet(path, tableName);
  }

  // Transaction support
  async beginTransaction(): Promise<void> {
    const api = this.getApi();

    if (this.inTransaction) {
      this.logger.warn('Transaction already in progress');
      return;
    }

    this.logger.debug('Begin transaction');
    await api.execute('BEGIN TRANSACTION');
    this.inTransaction = true;
  }

  async commit(): Promise<void> {
    const api = this.getApi();

    if (!this.inTransaction) {
      this.logger.warn('No transaction to commit');
      return;
    }

    this.logger.debug('Commit');
    await api.execute('COMMIT');
    this.inTransaction = false;
  }

  async rollback(): Promise<void> {
    const api = this.getApi();

    if (!this.inTransaction) {
      this.logger.warn('No transaction to rollback');
      return;
    }

    this.logger.debug('Rollback');
    await api.execute('ROLLBACK');
    this.inTransaction = false;
  }
}
