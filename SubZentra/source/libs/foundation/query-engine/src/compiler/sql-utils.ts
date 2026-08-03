/**
 * SQL Utilities for Foundation Query Engine
 *
 * Provides SQL escaping, quoting, and formatting utilities.
 * Reuses canonical SQL helpers from @open-zentra/foundation-bridge.
 *
 * @module compiler/sql-utils
 */

import {
  escapeString as bridgeEscapeString,
  isValidIdentifier as bridgeIsValidIdentifier,
  quoteIdentifier as bridgeQuoteIdentifier,
  validateIdentifier as bridgeValidateIdentifier,
} from '@open-zentra/foundation-bridge';

import type { FilterValue } from '../types/filter';
import { parseMemberRef } from '../utils/member-ref';

// =============================================================================
// STRING ESCAPING
// =============================================================================

/**
 * Escape a string value for use in SQL literals.
 *
 * Doubles single quotes so the value can be safely embedded in a
 * single-quoted SQL string. Prefer parameterized queries over string
 * escaping when possible.
 *
 * @param value - String to escape
 * @returns Escaped string (single quotes doubled)
 *
 * @example
 * escapeString("O'Brien") // "O''Brien"
 * escapeString("test")    // "test"
 */
export const escapeString = (value: string): string => bridgeEscapeString(value);

/**
 * Validate that a string matches SQL identifier pattern (pattern-only).
 * Does not check reserved words or length. For full DuckDB identifier validation
 * (pattern + length + reserved words), use validateIdentifier/isValidIdentifier
 * from @open-zentra/foundation-bridge.
 *
 * Valid identifiers start with a letter or underscore,
 * followed by letters, digits, or underscores.
 *
 * @param name - The identifier to validate
 * @returns True if the identifier matches the pattern
 */
export const isValidIdentifier = (name: string): boolean => {
  return bridgeIsValidIdentifier(name);
};

// =============================================================================
// IDENTIFIER QUOTING
// =============================================================================

/**
 * Quote an identifier for DuckDB (uses double quotes).
 * Accepts any string and returns a quoted identifier string.
 *
 * For the "validate then quote" flow, use validateIdentifier + quoteIdentifier from
 * `@open-zentra/foundation-bridge` (bridge takes validated SqlIdentifier, returns string).
 *
 * @param identifier - Raw identifier to quote
 * @returns Double-quoted identifier safe for SQL
 */
export const quoteIdentifier = (identifier: string): string => {
  try {
    const validatedIdentifier = bridgeValidateIdentifier(identifier);
    return bridgeQuoteIdentifier(validatedIdentifier);
  } catch {
    const escapedIdentifier = identifier.replace(/"/g, '""');
    return `"${escapedIdentifier}"`;
  }
};

/**
 * Quote a table name with optional schema
 */
export const quoteTableName = (tableName: string, schema?: string): string => {
  if (schema) {
    return `${quoteIdentifier(schema)}.${quoteIdentifier(tableName)}`;
  }
  return quoteIdentifier(tableName);
};

/**
 * Quote a column with optional table alias
 */
export const quoteColumn = (columnName: string, tableAlias?: string): string => {
  if (tableAlias) {
    return `${quoteIdentifier(tableAlias)}.${quoteIdentifier(columnName)}`;
  }
  return quoteIdentifier(columnName);
};

/**
 * Parse a member reference (table.column) and quote it.
 * Delegates to canonical member-ref parser.
 */
export const quoteMemberRef = (memberRef: string): string => {
  if (memberRef === '*') {
    return '*';
  }

  const parsed = parseMemberRef(memberRef);
  if (!parsed) {
    return quoteIdentifier(memberRef);
  }
  return `${quoteIdentifier(parsed.table)}.${quoteIdentifier(parsed.column)}`;
};

/**
 * Format a value for SQL
 */
export const formatValue = (value: FilterValue): string => {
  if (value === null) {
    return 'NULL';
  }
  if (typeof value === 'string') {
    return `'${escapeString(value)}'`;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'TRUE' : 'FALSE';
  }
  if (value instanceof Date) {
    return `'${value.toISOString()}'`;
  }
  return String(value);
};

/**
 * Format an array of values for SQL IN clause
 */
export const formatValueList = (values: ReadonlyArray<FilterValue>): string => {
  return values.map(formatValue).join(', ');
};

// =============================================================================
// PATTERN ESCAPING
// =============================================================================

/**
 * Escape a LIKE pattern (escape % and _ characters)
 */
export const escapeLikePattern = (pattern: string): string => {
  return pattern.replace(/\\/g, '\\\\').replace(/%/g, '\\%').replace(/_/g, '\\_');
};

/**
 * Build a LIKE pattern for "contains" operator
 */
export const buildContainsPattern = (value: string): string => {
  return `'%${escapeLikePattern(escapeString(value))}%'`;
};

/**
 * Build a LIKE pattern for "starts with" operator
 */
export const buildStartsWithPattern = (value: string): string => {
  return `'${escapeLikePattern(escapeString(value))}%'`;
};

/**
 * Build a LIKE pattern for "ends with" operator
 */
export const buildEndsWithPattern = (value: string): string => {
  return `'%${escapeLikePattern(escapeString(value))}'`;
};

// =============================================================================
// SQL FORMATTING
// =============================================================================

/**
 * Join clauses with a separator
 */
export const joinClauses = (clauses: ReadonlyArray<string>, separator = ' '): string => {
  return clauses.filter(Boolean).join(separator);
};

/**
 * Wrap in parentheses if needed
 */
export const wrapInParens = (sql: string): string => `(${sql})`;

/**
 * Format SQL with optional pretty printing
 */
export const formatSql = (sql: string, pretty = false): string => {
  if (!pretty) {
    // Normalize whitespace
    return sql.replace(/\s+/g, ' ').trim();
  }

  // Basic pretty printing
  const keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'OFFSET'];
  let result = sql;

  for (const keyword of keywords) {
    result = result.replace(new RegExp(`\\b${keyword}\\b`, 'gi'), `\n${keyword}`);
  }

  return result.trim();
};

// =============================================================================
// DATE/TIME UTILITIES
// =============================================================================

/**
 * Format a date for SQL
 */
export const formatDate = (date: Date | string): string => {
  if (typeof date === 'string') {
    return `'${escapeString(date)}'`;
  }
  return `'${date.toISOString().split('T')[0]}'`;
};

/**
 * Format a timestamp for SQL
 */
export const formatTimestamp = (date: Date | string): string => {
  if (typeof date === 'string') {
    return `'${escapeString(date)}'`;
  }
  return `'${date.toISOString()}'`;
};

/**
 * Build a date_trunc expression
 */
export const buildDateTrunc = (granularity: string, column: string): string => {
  return `date_trunc('${granularity}', ${column})`;
};

// =============================================================================
// AGGREGATE UTILITIES
// =============================================================================

/**
 * Build an aggregation expression
 */
export const buildAggregation = (
  func: string,
  column: string,
  distinct = false,
  filter?: string,
): string => {
  let expression: string;

  if (func === 'COUNT(DISTINCT') {
    expression = `COUNT(DISTINCT ${column})`;
  } else if (distinct && func !== 'COUNT') {
    expression = `${func}(DISTINCT ${column})`;
  } else if (func === 'COUNT' && column === '*') {
    expression = 'COUNT(*)';
  } else {
    expression = `${func}(${column})`;
  }

  if (filter) {
    expression += ` FILTER (WHERE ${filter})`;
  }

  return expression;
};

/**
 * Build a CASE expression
 */
export const buildCaseExpression = (
  conditions: ReadonlyArray<{ when: string; then: string }>,
  elseValue?: string,
): string => {
  const whenClauses = conditions.map(({ when, then }) => `WHEN ${when} THEN ${then}`).join(' ');

  if (elseValue !== undefined) {
    return `CASE ${whenClauses} ELSE ${elseValue} END`;
  }
  return `CASE ${whenClauses} END`;
};

// =============================================================================
// VALIDATION
// =============================================================================

/**
 * Sanitize an identifier (remove invalid characters)
 */
export const sanitizeIdentifier = (identifier: string): string => {
  // Replace invalid characters with underscore
  return identifier.replace(/[^a-zA-Z0-9_]/g, '_');
};
