/**
 * SQL Compiler Module for Foundation Query Engine
 *
 * Provides SQL compilation from Query to DuckDB SQL.
 * SQL utility primitives are reused from foundation-bridge and wrapped with
 * query-engine-specific composition helpers.
 *
 * @module compiler
 */

// =============================================================================
// SQL Compiler
// =============================================================================

export {
  SqlCompiler,
  QueryCompilationError,
  createSqlCompiler,
  getSqlCompiler,
  resetSqlCompiler,
  hasSqlCompilerInstance,
  QUOTE_STYLES,
  type QuoteStyle,
  SQL_DIALECTS,
  type SqlDialect,
  type SqlCompilerConfig,
  type CompilationResult,
  type CompileOptions,
} from './sql-compiler';

// =============================================================================
// SQL Utilities (bridge-backed + query-engine composition helpers)
// =============================================================================

export {
  // String escaping
  escapeString,
  isValidIdentifier,
  // Identifier quoting
  quoteIdentifier,
  quoteTableName,
  quoteColumn,
  quoteMemberRef,
  // Value formatting
  formatValue,
  formatValueList,
  // Pattern building
  escapeLikePattern,
  buildContainsPattern,
  buildStartsWithPattern,
  buildEndsWithPattern,
  // SQL formatting
  joinClauses,
  wrapInParens,
  formatSql,
  // Date/time utilities
  formatDate,
  formatTimestamp,
  buildDateTrunc,
  // Aggregate utilities
  buildAggregation,
  buildCaseExpression,
  // Validation
  sanitizeIdentifier,
} from './sql-utils';
