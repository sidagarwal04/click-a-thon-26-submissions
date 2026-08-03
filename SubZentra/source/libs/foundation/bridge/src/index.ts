/**
 * @foundation/bridge
 *
 * Bridge layer for environment detection, DuckDB routing, and analytics.
 * Abstracts WASM vs Native DuckDB implementations.
 * Depends on: @foundation/database, @foundation/data-model
 *
 * @packageDocumentation
 */

// ============================================================================
// DuckDB Router (used by data-layer)
// ============================================================================

export { DuckDBRouter, getDuckDBRouter, resetDuckDBRouter } from './duckdb/router';

// ============================================================================
// DuckDB Types (used by data-layer)
// ============================================================================

export type { DuckDBRow, DuckDBResult } from './duckdb/types';

// ============================================================================
// SQL Utilities (used by query-engine, data-layer)
// ============================================================================

export {
  validateIdentifier,
  validateTableName,
  isValidIdentifier,
  quoteIdentifier,
  escapeString,
  validateViewSql,
  buildCreateViewSql,
  buildDropViewSql,
  buildParameterizedSql,
  applyLimitOffset,
} from './utils/sql';
