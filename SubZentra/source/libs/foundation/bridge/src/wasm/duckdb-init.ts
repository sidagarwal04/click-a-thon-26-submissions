/**
 * DuckDB WASM Initialization Module
 *
 * Uses DuckDB's official bundle manifest helper.
 * This avoids build-tool-specific `?url` module typing issues across projects.
 *
 * @module wasm/duckdb-init
 */

import * as duckdb from '@duckdb/duckdb-wasm';

/**
 * DuckDB-WASM bundle manifest.
 *
 * getJsDelivrBundles() returns official CDN bundle URLs for both `mvp` and `eh`
 * variants. selectBundle() chooses the best one based on browser capabilities.
 */
const MANUAL_BUNDLES: duckdb.DuckDBBundles = duckdb.getJsDelivrBundles();

/**
 * Result of DuckDB initialization
 */
export interface DuckDBInstance {
  /** The DuckDB database instance */
  db: duckdb.AsyncDuckDB;
  /** An open connection to the database */
  conn: duckdb.AsyncDuckDBConnection;
  /** The worker instance (for cleanup) */
  worker: Worker;
}

/**
 * Creates and initializes a DuckDB-WASM instance
 *
 * This function:
 * 1. Selects the best WASM bundle based on browser capabilities
 * 2. Creates a Web Worker for DuckDB operations
 * 3. Instantiates the WASM module
 * 4. Opens a database connection
 *
 * @param logger - Optional custom logger (defaults to ConsoleLogger)
 * @returns Promise resolving to the initialized DuckDB instance
 *
 * @example
 * ```typescript
 * const { db, conn, worker } = await createDuckDBInstance();
 * const result = await conn.query('SELECT 1 as value');
 * ```
 */
export const createDuckDBInstance = async (logger?: duckdb.Logger): Promise<DuckDBInstance> => {
  // Select the best bundle based on browser capabilities
  const bundle = await duckdb.selectBundle(MANUAL_BUNDLES);
  if (!bundle.mainWorker) {
    throw new Error('DuckDB bundle is missing a mainWorker entry');
  }

  // Create the worker from the selected bundle
  const worker = new Worker(bundle.mainWorker);

  // Create the async DuckDB instance
  const db = new duckdb.AsyncDuckDB(logger ?? new duckdb.ConsoleLogger(), worker);

  // Instantiate the WASM module
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);

  // Open a connection
  const conn = await db.connect();

  return { db, conn, worker };
};
