/**
 * DuckDB types
 *
 * For other types, import directly from their source:
 * - Bridge types: import from '../types/bridge'
 * - Branded types: import from '@open-zentra/foundation-data-model'
 *
 * @module duckdb/types
 */

import type { QueryResult } from '../types/bridge';

/**
 * Generic DuckDB row type
 */
export type DuckDBRow = Record<string, unknown>;

/**
 * Alias for QueryResult for backward compatibility
 */
export type DuckDBResult<T extends DuckDBRow = DuckDBRow> = QueryResult<T>;
