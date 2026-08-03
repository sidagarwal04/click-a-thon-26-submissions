/**
 * SQL sanitization and query building utilities
 *
 * Provides functions to safely handle SQL identifiers and prevent injection.
 *
 * @module utils/sql
 */

import type { SqlIdentifier, SqlTableName } from '@open-zentra/foundation-data-model';

import { SQL } from '../constants';
import { SqlValidationError } from '../errors/query-errors';

// =============================================================================
// Constants (imported from centralized constants)
// =============================================================================

/** Valid SQL identifier pattern */
const SQL_IDENTIFIER_PATTERN = SQL.IDENTIFIER_PATTERN;

/** Maximum identifier length (DuckDB limit) */
const MAX_IDENTIFIER_LENGTH = SQL.MAX_IDENTIFIER_LENGTH;

/** SQL reserved words that cannot be used as identifiers (as Set for O(1) lookup) */
const RESERVED_WORDS: Set<string> = new Set(SQL.RESERVED_WORDS);

// =============================================================================
// Memoization Cache for Validated Identifiers
// =============================================================================

/** Maximum number of cached validated identifiers */
const MAX_VALIDATION_CACHE_SIZE = 1000;

/**
 * Cache for validated SQL identifiers
 * Using Map to maintain insertion order for LRU-style eviction
 */
const validatedIdentifiersCache = new Map<string, SqlIdentifier>();

/**
 * Cache for invalid identifiers (to avoid re-validating known bad inputs)
 */
const invalidIdentifiersCache = new Set<string>();

/**
 * Add a validated identifier to the cache with LRU eviction
 */
const cacheValidatedIdentifier = (name: string, identifier: SqlIdentifier): void => {
  // Evict oldest entries if cache is full
  if (validatedIdentifiersCache.size >= MAX_VALIDATION_CACHE_SIZE) {
    const firstKey = validatedIdentifiersCache.keys().next().value;
    if (firstKey !== undefined) {
      validatedIdentifiersCache.delete(firstKey);
    }
  }
  validatedIdentifiersCache.set(name, identifier);
};

/**
 * Mark an identifier as invalid in the cache
 */
const cacheInvalidIdentifier = (name: string): void => {
  // Limit invalid cache size to prevent unbounded growth
  if (invalidIdentifiersCache.size >= MAX_VALIDATION_CACHE_SIZE) {
    // Clear the entire set when full (simple approach)
    invalidIdentifiersCache.clear();
  }
  invalidIdentifiersCache.add(name);
};

// =============================================================================
// Validation Functions
// =============================================================================

/**
 * Validate and create a safe SQL identifier
 *
 * Uses memoization to cache validation results for frequently used identifiers.
 *
 * @param name - The identifier to validate
 * @returns Validated SqlIdentifier
 * @throws SqlValidationError if identifier is invalid
 *
 * @example
 * ```typescript
 * const safeName = validateIdentifier('users'); // OK
 * const safeName = validateIdentifier('user_table'); // OK
 * validateIdentifier(''); // throws SqlValidationError
 * validateIdentifier('1table'); // throws SqlValidationError
 * validateIdentifier('DROP'); // throws SqlValidationError
 * ```
 */
export const validateIdentifier = (name: string): SqlIdentifier => {
  // Check cache for previously validated identifiers
  const cached = validatedIdentifiersCache.get(name);
  if (cached !== undefined) {
    return cached;
  }

  // Check if known to be invalid
  if (invalidIdentifiersCache.has(name)) {
    throw new SqlValidationError(name, 'Identifier is invalid (cached)');
  }

  // Perform validation
  if (!name || name.length === 0) {
    cacheInvalidIdentifier(name ?? '');
    throw new SqlValidationError(name ?? '', 'Identifier cannot be empty');
  }

  if (name.length > MAX_IDENTIFIER_LENGTH) {
    cacheInvalidIdentifier(name);
    throw new SqlValidationError(
      name,
      `Identifier exceeds maximum length of ${MAX_IDENTIFIER_LENGTH}`,
    );
  }

  if (!SQL_IDENTIFIER_PATTERN.test(name)) {
    cacheInvalidIdentifier(name);
    throw new SqlValidationError(
      name,
      'Identifier must start with letter or underscore and contain only alphanumeric characters or underscores',
    );
  }

  if (RESERVED_WORDS.has(name.toUpperCase())) {
    cacheInvalidIdentifier(name);
    throw new SqlValidationError(name, 'Identifier is a SQL reserved word');
  }

  // Cache the validated result (cast is safe: validation above guarantees valid identifier)
  const identifier = name as SqlIdentifier;
  cacheValidatedIdentifier(name, identifier);

  return identifier;
};

/**
 * Validate table name (same rules as identifier)
 *
 * @param name - The table name to validate
 * @returns Validated SqlTableName
 * @throws SqlValidationError if name is invalid
 */
export const validateTableName = (name: string): SqlTableName => {
  validateIdentifier(name);
  // Cast is safe: validateIdentifier guarantees valid identifier
  return name as SqlTableName;
};

/**
 * Check if a string is a valid SQL identifier without throwing
 *
 * @param value - Value to check
 * @returns true if valid identifier
 */
export const isValidIdentifier = (value: unknown): value is string => {
  if (typeof value !== 'string') return false;
  if (value.length === 0 || value.length > MAX_IDENTIFIER_LENGTH) return false;
  if (!SQL_IDENTIFIER_PATTERN.test(value)) return false;
  if (RESERVED_WORDS.has(value.toUpperCase())) return false;
  return true;
};

// =============================================================================
// View SQL Validation
// =============================================================================

/**
 * DDL/DML keywords that must not appear in view SQL outside quoted strings.
 * View definitions should only contain SELECT-like statements.
 */
const FORBIDDEN_VIEW_SQL_KEYWORDS: ReadonlySet<string> = new Set([
  'DROP',
  'CREATE',
  'ALTER',
  'DELETE',
  'INSERT',
  'UPDATE',
  'TRUNCATE',
  'GRANT',
  'REVOKE',
  'EXEC',
  'EXECUTE',
]);

/**
 * Strip single-quoted and double-quoted strings from SQL so keyword checks
 * only examine non-literal portions. Handles escaped quotes ('' and "").
 */
const stripQuotedStrings = (sql: string): string =>
  sql.replace(/'(?:[^']|'')*'/g, '').replace(/"(?:[^"]|"")*"/g, '');

/**
 * Validate that a SQL string is safe for use as a view definition.
 *
 * Rejects SQL containing DDL/DML keywords (DROP, CREATE, ALTER, DELETE,
 * INSERT, UPDATE, TRUNCATE, etc.) outside of quoted strings and requires
 * the statement to start with a SELECT-like keyword.
 *
 * @param sql - The SQL statement to validate
 * @throws SqlValidationError if the SQL contains forbidden keywords or
 *         doesn't look like a SELECT statement
 *
 * @example
 * ```typescript
 * validateViewSql('SELECT * FROM users WHERE active = true'); // OK
 * validateViewSql('DROP TABLE users; SELECT 1'); // throws SqlValidationError
 * ```
 */
export const validateViewSql = (sql: string): void => {
  if (!sql || sql.trim().length === 0) {
    throw new SqlValidationError('(empty)', 'View SQL cannot be empty');
  }

  const stripped = stripQuotedStrings(sql);

  // Check that the statement starts with SELECT or WITH (CTEs)
  const trimmedUpper = stripped.trim().toUpperCase();
  if (!trimmedUpper.startsWith('SELECT') && !trimmedUpper.startsWith('WITH')) {
    throw new SqlValidationError(sql.slice(0, 50), 'View SQL must start with SELECT or WITH');
  }

  // Check for forbidden keywords as whole words in the non-quoted portion.
  // Use word boundary (\b) to avoid matching partial words (e.g. "UPDATED_AT")
  for (const keyword of FORBIDDEN_VIEW_SQL_KEYWORDS) {
    const pattern = new RegExp(`\\b${keyword}\\b`, 'i');
    if (pattern.test(stripped)) {
      throw new SqlValidationError(
        sql.slice(0, 50),
        `View SQL contains forbidden keyword: ${keyword}`,
      );
    }
  }
};

// =============================================================================
// SQL Building Functions
// =============================================================================

/**
 * Quote an identifier for use in SQL
 * Handles double-quote escaping
 *
 * @param identifier - Validated identifier to quote
 * @returns Quoted identifier string
 *
 * @example
 * ```typescript
 * quoteIdentifier('users' as SqlIdentifier); // '"users"'
 * quoteIdentifier('user"name' as SqlIdentifier); // '"user""name"'
 * ```
 */
export const quoteIdentifier = (identifier: SqlIdentifier): string => {
  return `"${identifier.replace(/"/g, '""')}"`;
};

/**
 * Build a safe CREATE VIEW statement
 *
 * @param viewName - Validated view name
 * @param sql - SQL SELECT statement for the view
 * @param orReplace - Whether to use CREATE OR REPLACE (default: true)
 * @returns Complete CREATE VIEW SQL statement
 *
 * @example
 * ```typescript
 * const sql = buildCreateViewSql(
 *   validateIdentifier('active_users'),
 *   'SELECT * FROM users WHERE active = true'
 * );
 * // 'CREATE OR REPLACE VIEW "active_users" AS SELECT * FROM users WHERE active = true'
 * ```
 */
export const buildCreateViewSql = (
  viewName: SqlIdentifier,
  sql: string,
  orReplace = true,
): string => {
  const prefix = orReplace ? 'CREATE OR REPLACE VIEW' : 'CREATE VIEW';
  return `${prefix} ${quoteIdentifier(viewName)} AS ${sql}`;
};

/**
 * Build a safe DROP VIEW statement
 *
 * @param viewName - Validated view name
 * @param ifExists - Whether to use IF EXISTS (default: true)
 * @returns Complete DROP VIEW SQL statement
 */
export const buildDropViewSql = (viewName: SqlIdentifier, ifExists = true): string => {
  const suffix = ifExists ? ' IF EXISTS' : '';
  return `DROP VIEW${suffix} ${quoteIdentifier(viewName)}`;
};

/**
 * Escape a string value for use in SQL literals.
 *
 * Doubles single quotes so the value can be safely embedded in a
 * single-quoted SQL string. Prefer parameterized queries over string
 * escaping when possible.
 *
 * @param value - String to escape
 * @returns Escaped string (single quotes doubled)
 */
export const escapeString = (value: string): string => value.replace(/'/g, "''");

/**
 * Build a parameterized SQL string with placeholders
 *
 * @param sql - SQL template with ? placeholders
 * @param paramCount - Expected number of parameters
 * @returns Object with sql and placeholder info
 */
export const buildParameterizedSql = (
  sql: string,
  paramCount: number,
): { sql: string; placeholderCount: number } => {
  const placeholderCount = (sql.match(/\?/g) || []).length;

  if (placeholderCount !== paramCount) {
    throw new SqlValidationError(
      sql.slice(0, 50),
      `Expected ${paramCount} parameters but found ${placeholderCount} placeholders`,
    );
  }

  return { sql, placeholderCount };
};

/**
 * Apply LIMIT and OFFSET to a SQL query if not already present
 *
 * @param sql - Base SQL query
 * @param limit - Maximum rows to return
 * @param offset - Number of rows to skip
 * @returns SQL with LIMIT/OFFSET applied
 */
export const applyLimitOffset = (sql: string, limit?: number, offset?: number): string => {
  if (limit !== undefined && limit < 0) {
    throw new SqlValidationError(String(limit), 'LIMIT must be a non-negative number');
  }

  if (offset !== undefined && offset < 0) {
    throw new SqlValidationError(String(offset), 'OFFSET must be a non-negative number');
  }

  let result = sql;

  // Only add LIMIT if not already present
  if (limit !== undefined && !/\bLIMIT\b/i.test(sql)) {
    result += ` LIMIT ${Math.floor(limit)}`;

    // Only add OFFSET if LIMIT is also being added
    if (offset !== undefined) {
      result += ` OFFSET ${Math.floor(offset)}`;
    }
  }

  return result;
};
