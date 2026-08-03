/**
 * SQL Compiler
 *
 * Compiles Query to DuckDB SQL.
 * Handles object-based DimensionSpec, MeasureSpec, JoinSpec.
 *
 * @module compiler/sql-compiler
 */

import {
  createSingletonFactory,
  DisposedError,
  hashPayloadSync,
  type IDisposable,
} from '@open-zentra/foundation-utils';

import { mapFilterExpression } from '../internal/filter-recursion';
import { getAggregationSqlFunction, isDistinctAggregation } from '../types/aggregation';
import type { DimensionSpec } from '../types/dimension';
import type { FilterCondition, FilterExpression, FilterPrimitive } from '../types/filter';
import { operatorRequiresValues } from '../types/filter';
import type { JoinSpec } from '../types/join';
import { getJoinSqlKeyword } from '../types/join';
import type { MeasureSpec } from '../types/measure';
import type { OrderBySpec } from '../types/order';
import type { Query } from '../types/query';
import type { DateRangeSpec, TimeDimensionSpec, TimeGranularity } from '../types/time';
import {
  getDateTruncUnit,
  isDateRange,
  isDateRangeTuple,
  isPresetDateRange,
  isRelativeDateRange,
  resolvePresetDateRange,
} from '../types/time';
import { parseMemberRef } from '../utils/member-ref';
import {
  formatSql,
  formatValue as utilFormatValue,
  quoteIdentifier as utilQuoteIdentifier,
} from './sql-utils';

// =============================================================================
// ERRORS
// =============================================================================

/**
 * Error thrown when SQL compilation fails due to invalid query structure.
 */
export class QueryCompilationError extends Error {
  readonly code = 'QUERY_COMPILATION_ERROR' as const;

  constructor(message: string) {
    super(message);
    this.name = 'QueryCompilationError';
  }
}

// =============================================================================
// CONFIGURATION
// =============================================================================

/**
 * Supported identifier quoting styles.
 */
export const QUOTE_STYLES = {
  DOUBLE: 'double',
  BACKTICK: 'backtick',
  BRACKET: 'bracket',
} as const;

export type QuoteStyle = (typeof QUOTE_STYLES)[keyof typeof QUOTE_STYLES];

/**
 * Supported SQL dialects.
 */
export const SQL_DIALECTS = {
  DUCKDB: 'duckdb',
  POSTGRES: 'postgres',
  SQLITE: 'sqlite',
} as const;

export type SqlDialect = (typeof SQL_DIALECTS)[keyof typeof SQL_DIALECTS];

/**
 * Configuration options for the SQL compiler.
 */
export interface SqlCompilerConfig {
  /** Quote style for identifiers ('double' for DuckDB) */
  readonly quoteStyle?: QuoteStyle;
  /** SQL dialect */
  readonly dialect?: SqlDialect;
  /** Include SQL comments */
  readonly includeComments?: boolean;
  /** Pretty print the SQL */
  readonly prettyPrint?: boolean;
  /** Default schema */
  readonly defaultSchema?: string;
}

/**
 * Resolved configuration with defaults.
 */
interface ResolvedConfig {
  readonly quoteStyle: QuoteStyle;
  readonly dialect: SqlDialect;
  readonly includeComments: boolean;
  readonly prettyPrint: boolean;
  readonly defaultSchema: string;
}

const DEFAULT_COMPILER_CONFIG: ResolvedConfig = {
  quoteStyle: QUOTE_STYLES.DOUBLE,
  dialect: SQL_DIALECTS.DUCKDB,
  includeComments: false,
  prettyPrint: false,
  defaultSchema: '',
};

// =============================================================================
// SQL UTILITIES
// =============================================================================

/**
 * Quote an identifier (table name, column name).
 */
const quoteIdentifier = (identifier: string): string => {
  return utilQuoteIdentifier(identifier);
};

/**
 * Quote a table.column reference.
 */
const quoteMemberRef = (member: string): string => {
  const parsed = parseMemberRef(member);
  if (!parsed) {
    return quoteIdentifier(member);
  }
  return `${quoteIdentifier(parsed.table)}.${quoteIdentifier(parsed.column)}`;
};

/**
 * Format a value for SQL.
 */
const formatValue = (value: FilterPrimitive): string => {
  return utilFormatValue(value);
};

/**
 * Format an array of values for SQL (for IN operator).
 */
const formatValueList = (values: ReadonlyArray<FilterPrimitive>): string => {
  return `(${values.map(formatValue).join(', ')})`;
};

const getStringFilterValue = (value: FilterPrimitive): string =>
  typeof value === 'string' ? value : String(value);

/**
 * Build LIKE pattern for string operators.
 */
const buildLikePattern = (value: string, operator: LikePatternOperator): string => {
  // Escape special LIKE characters and single quotes
  const escaped = value.replace(/[%_\\]/g, '\\$&').replace(/'/g, "''");

  switch (operator) {
    case 'contains':
      return `'%${escaped}%'`;
    case 'startsWith':
      return `'${escaped}%'`;
    case 'endsWith':
      return `'%${escaped}'`;
  }
};

const LIKE_PATTERN_OPERATORS = {
  CONTAINS: 'contains',
  STARTS_WITH: 'startsWith',
  ENDS_WITH: 'endsWith',
} as const;

type LikePatternOperator = (typeof LIKE_PATTERN_OPERATORS)[keyof typeof LIKE_PATTERN_OPERATORS];

// =============================================================================
// COMPILATION RESULT
// =============================================================================

/**
 * Result of SQL compilation.
 */
export interface CompilationResult {
  /** Generated SQL query */
  readonly sql: string;
  /** Tables involved in the query */
  readonly tables: ReadonlyArray<string>;
  /** Whether query has aggregations */
  readonly hasAggregations: boolean;
  /** Whether query has joins */
  readonly hasJoins: boolean;
  /** Parameters for prepared statement (if any) */
  readonly parameters?: ReadonlyArray<unknown>;
}

// =============================================================================
// COMPILE OPTIONS
// =============================================================================

/**
 * Options for compilation.
 */
export interface CompileOptions {
  /** Override primary table */
  readonly primaryTable?: string;
  /** Pretty print output */
  readonly pretty?: boolean;
}

// =============================================================================
// FILTER COMPILATION
// =============================================================================

/**
 * Validate that a filter condition has the required values for its operator.
 * Throws QueryCompilationError if values are missing for operators that require them.
 */
const validateFilterValues = (
  condition: FilterCondition,
  values: ReadonlyArray<FilterPrimitive>,
): void => {
  if (!operatorRequiresValues(condition.operator)) {
    return;
  }

  if (values.length === 0) {
    throw new QueryCompilationError(
      `Filter operator '${condition.operator}' on member '${condition.member}' requires at least one value, but none were provided`,
    );
  }

  if (condition.operator === 'between' && values.length < 2) {
    throw new QueryCompilationError(
      `Filter operator 'between' on member '${condition.member}' requires exactly 2 values, but ${values.length} were provided`,
    );
  }
};

/**
 * Compile a single filter condition to a SQL WHERE clause fragment.
 *
 * Maps each FilterOperator to its SQL equivalent (e.g. `equals` → `=`, `in` → `IN`).
 *
 * @param condition - The filter condition with member, operator, and optional values
 * @returns SQL string for the condition
 * @throws QueryCompilationError for unknown operators or missing required values
 */
const compileFilterCondition = (condition: FilterCondition): string => {
  const memberRef = quoteMemberRef(condition.member);
  const values = condition.values ?? [];

  // Validate values before compiling
  validateFilterValues(condition, values);

  switch (condition.operator) {
    // Equality operators
    case 'equals':
      return `${memberRef} = ${formatValue(values[0])}`;

    case 'notEquals':
      return `${memberRef} != ${formatValue(values[0])}`;

    // Comparison operators
    case 'gt':
      return `${memberRef} > ${formatValue(values[0])}`;

    case 'gte':
      return `${memberRef} >= ${formatValue(values[0])}`;

    case 'lt':
      return `${memberRef} < ${formatValue(values[0])}`;

    case 'lte':
      return `${memberRef} <= ${formatValue(values[0])}`;

    case 'between':
      return `${memberRef} BETWEEN ${formatValue(values[0])} AND ${formatValue(values[1])}`;

    // Set operators
    case 'in':
      if (values.length === 0) return 'FALSE';
      return `${memberRef} IN ${formatValueList(values)}`;

    case 'notIn':
      if (values.length === 0) return 'TRUE';
      return `${memberRef} NOT IN ${formatValueList(values)}`;

    // String operators
    case 'contains':
      return `${memberRef} LIKE ${buildLikePattern(
        getStringFilterValue(values[0]),
        LIKE_PATTERN_OPERATORS.CONTAINS,
      )} ESCAPE '\\'`;

    case 'notContains':
      return `${memberRef} NOT LIKE ${buildLikePattern(
        getStringFilterValue(values[0]),
        LIKE_PATTERN_OPERATORS.CONTAINS,
      )} ESCAPE '\\'`;

    case 'startsWith':
      return `${memberRef} LIKE ${buildLikePattern(
        getStringFilterValue(values[0]),
        LIKE_PATTERN_OPERATORS.STARTS_WITH,
      )} ESCAPE '\\'`;

    case 'endsWith':
      return `${memberRef} LIKE ${buildLikePattern(
        getStringFilterValue(values[0]),
        LIKE_PATTERN_OPERATORS.ENDS_WITH,
      )} ESCAPE '\\'`;

    case 'matches':
      return `${memberRef} ~ ${formatValue(values[0])}`;

    // Null operators
    case 'isNull':
      return `${memberRef} IS NULL`;

    case 'isNotNull':
      return `${memberRef} IS NOT NULL`;

    // Array operators (DuckDB list functions)
    case 'arrayContains':
      return `list_contains(${memberRef}, ${formatValue(values[0])})`;

    case 'arrayContainsAny':
      if (values.length === 0) return 'FALSE';
      return `list_has_any(${memberRef}, [${values.map(formatValue).join(', ')}])`;

    case 'arrayContainsAll':
      if (values.length === 0) return 'TRUE';
      return `list_has_all(${memberRef}, [${values.map(formatValue).join(', ')}])`;

    default: {
      // Exhaustive check: unknown operators must fail loudly
      const unknownOp: string = condition.operator;
      throw new QueryCompilationError(
        `Unknown filter operator '${unknownOp}' on member '${condition.member}'. ` +
          `Valid operators: equals, notEquals, gt, gte, lt, lte, between, in, notIn, ` +
          `contains, notContains, startsWith, endsWith, matches, isNull, isNotNull, ` +
          `arrayContains, arrayContainsAny, arrayContainsAll`,
      );
    }
  }
};

/**
 * Compile a filter expression (condition, AND group, or OR group) to a SQL WHERE clause fragment.
 *
 * Recursively handles nested AND/OR groups.
 *
 * @param expression - The filter expression to compile
 * @returns SQL string for the expression
 */
const compileFilterExpression = (expression: FilterExpression): string =>
  mapFilterExpression(expression, {
    onCondition: compileFilterCondition,
    onAndGroup: (children) =>
      children.length > 1 ? `(${children.join(' AND ')})` : children[0] ?? 'TRUE',
    onOrGroup: (children) =>
      children.length > 1 ? `(${children.join(' OR ')})` : children[0] ?? 'TRUE',
  });

// =============================================================================
// SELECT COMPILATION
// =============================================================================

/**
 * Compile a dimension to SELECT expression.
 */
const compileDimensionSelect = (dimension: DimensionSpec): string => {
  const memberRef = quoteMemberRef(dimension.member);
  const alias = dimension.alias ?? parseMemberRef(dimension.member)?.column ?? dimension.member;
  return `${memberRef} AS ${quoteIdentifier(alias)}`;
};

/**
 * Compile a measure to SELECT expression.
 */
const compileMeasureSelect = (measure: MeasureSpec): string => {
  const memberRef = quoteMemberRef(measure.member);
  const aggFunc = getAggregationSqlFunction(measure.aggregation);
  const useDistinct = isDistinctAggregation(measure.aggregation) || measure.distinct;

  let expr: string;

  // Handle filtered aggregation
  if (measure.filter) {
    const filterCondition = compileFilterCondition(measure.filter);
    expr = useDistinct
      ? `${aggFunc}(DISTINCT CASE WHEN ${filterCondition} THEN ${memberRef} END)`
      : `${aggFunc}(CASE WHEN ${filterCondition} THEN ${memberRef} END)`;
  } else {
    expr = useDistinct ? `${aggFunc}(DISTINCT ${memberRef})` : `${aggFunc}(${memberRef})`;
  }

  // Get alias
  const parsed = parseMemberRef(measure.member);
  const alias = measure.alias ?? `${measure.aggregation}_${parsed?.column ?? 'value'}`;

  return `${expr} AS ${quoteIdentifier(alias)}`;
};

// =============================================================================
// JOIN COMPILATION
// =============================================================================

/**
 * Compile an array of JoinSpec into SQL JOIN clauses.
 *
 * Tracks already-joined tables to determine which side of each join
 * introduces a new table. Supports additional join conditions.
 *
 * @param joins - Array of join specifications
 * @param primaryTable - The primary (FROM) table name
 * @returns Newline-separated SQL JOIN clauses, or empty string if no joins
 */
const compileJoinClauses = (joins: ReadonlyArray<JoinSpec>, primaryTable: string): string => {
  if (joins.length === 0) return '';

  const clauses: string[] = [];
  const joinedTables = new Set<string>([primaryTable]);

  for (const join of joins) {
    const leftParsed = parseMemberRef(join.left);
    const rightParsed = parseMemberRef(join.right);

    if (!leftParsed || !rightParsed) continue;

    // Determine which table to join
    const tableToJoin = joinedTables.has(leftParsed.table) ? rightParsed.table : leftParsed.table;

    joinedTables.add(tableToJoin);

    const joinKeyword = getJoinSqlKeyword(join.type);
    const leftRef = quoteMemberRef(join.left);
    const rightRef = quoteMemberRef(join.right);

    let joinClause = `${joinKeyword} ${quoteIdentifier(tableToJoin)} ON ${leftRef} = ${rightRef}`;

    // Add additional conditions
    if (join.additionalConditions) {
      const extraConditions = join.additionalConditions
        .map((cond) => `${quoteMemberRef(cond.left)} = ${quoteMemberRef(cond.right)}`)
        .join(' AND ');
      joinClause += ` AND ${extraConditions}`;
    }

    clauses.push(joinClause);
  }

  return clauses.join('\n');
};

// =============================================================================
// ORDER BY COMPILATION
// =============================================================================

/**
 * Compile an array of OrderBySpec into a SQL ORDER BY clause.
 *
 * @param orderBy - Array of order-by specifications with member, direction, and optional nulls handling
 * @returns SQL ORDER BY clause string, or empty string if no order specs
 */
const compileOrderByClause = (orderBy: ReadonlyArray<OrderBySpec>): string => {
  if (orderBy.length === 0) return '';

  const parts = orderBy.map((spec) => {
    const memberRef = quoteMemberRef(spec.member);
    const direction = spec.direction.toUpperCase();
    const nulls = spec.nulls ? ` NULLS ${spec.nulls.toUpperCase()}` : '';
    return `${memberRef} ${direction}${nulls}`;
  });

  return `ORDER BY ${parts.join(', ')}`;
};

// =============================================================================
// TIME DIMENSION COMPILATION
// =============================================================================

/**
 * Resolve a DateRangeSpec to absolute { from, to } date strings.
 */
const resolveDateRange = (dateRange: DateRangeSpec): { from: string; to: string } | null => {
  if (isPresetDateRange(dateRange)) {
    const resolved = resolvePresetDateRange(dateRange);
    return resolved;
  }

  if (isDateRange(dateRange)) {
    return { from: dateRange.from, to: dateRange.to };
  }

  if (isDateRangeTuple(dateRange)) {
    return { from: dateRange[0], to: dateRange[1] };
  }

  if (isRelativeDateRange(dateRange)) {
    // For relative date ranges, calculate from the reference date
    const now = new Date();
    const end = new Date(now);
    end.setHours(23, 59, 59, 999);

    const start = new Date(now);
    const unitMultipliers: Record<string, () => void> = {
      second: () => start.setSeconds(start.getSeconds() - dateRange.value),
      minute: () => start.setMinutes(start.getMinutes() - dateRange.value),
      hour: () => start.setHours(start.getHours() - dateRange.value),
      day: () => start.setDate(start.getDate() - dateRange.value),
      week: () => start.setDate(start.getDate() - dateRange.value * 7),
      month: () => start.setMonth(start.getMonth() - dateRange.value),
      quarter: () => start.setMonth(start.getMonth() - dateRange.value * 3),
      year: () => start.setFullYear(start.getFullYear() - dateRange.value),
    };

    const adjust = unitMultipliers[dateRange.unit];
    if (adjust) {
      adjust();
    }

    start.setHours(0, 0, 0, 0);

    const formatDate = (d: Date): string => d.toISOString().split('T')[0];
    return { from: formatDate(start), to: formatDate(end) };
  }

  return null;
};

/**
 * Compile a time dimension to a SELECT expression with DATE_TRUNC.
 */
const compileTimeDimensionSelect = (
  timeDim: TimeDimensionSpec,
  granularity: TimeGranularity,
): string => {
  const memberRef = quoteMemberRef(timeDim.dimension);
  const truncUnit = getDateTruncUnit(granularity);
  const parsed = parseMemberRef(timeDim.dimension);
  const alias = parsed ? `${parsed.column}_${truncUnit}` : `time_${truncUnit}`;
  return `DATE_TRUNC('${truncUnit}', ${memberRef}) AS ${quoteIdentifier(alias)}`;
};

/**
 * Compile a time dimension's date range to a WHERE clause fragment.
 */
const compileTimeDimensionFilter = (
  timeDim: TimeDimensionSpec,
  dateRange: DateRangeSpec,
): string | null => {
  const resolved = resolveDateRange(dateRange);
  if (!resolved) return null;

  const memberRef = quoteMemberRef(timeDim.dimension);
  return `${memberRef} BETWEEN '${resolved.from}' AND '${resolved.to}'`;
};

// =============================================================================
// SQL COMPILATION CACHE
// =============================================================================

/**
 * Default cache size for compiled SQL.
 */
const DEFAULT_CACHE_SIZE = 100;

/**
 * Cache entry for compiled SQL.
 */
interface CacheEntry {
  readonly result: CompilationResult;
}

/**
 * LRU cache for compiled SQL queries.
 * Prevents re-compilation of identical queries.
 */
class SqlCompilationCache {
  private readonly cache = new Map<string, CacheEntry>();
  private readonly maxSize: number;

  constructor(maxSize: number = DEFAULT_CACHE_SIZE) {
    this.maxSize = maxSize;
  }

  /**
   * Get a cached compilation result.
   *
   * Uses Map delete+set to move the entry to the end (most-recently-used).
   * Both operations are O(1) and this is the idiomatic approach for
   * Map-based LRU caches in JavaScript.
   */
  get(key: string): CompilationResult | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    // Move to end (most recently used)
    this.cache.delete(key);
    this.cache.set(key, entry);

    return entry.result;
  }

  /**
   * Set a compilation result in the cache.
   */
  set(key: string, result: CompilationResult): void {
    // If the key already exists, delete first so size check is accurate
    if (this.cache.has(key)) {
      this.cache.delete(key);
    }

    // Remove oldest entry if at capacity
    if (this.cache.size >= this.maxSize) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey !== undefined) {
        this.cache.delete(oldestKey);
      }
    }

    this.cache.set(key, { result });
  }

  /**
   * Clear the cache.
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get cache statistics.
   */
  getStats(): { size: number; maxSize: number } {
    return { size: this.cache.size, maxSize: this.maxSize };
  }
}

// =============================================================================
// SQL COMPILER CLASS
// =============================================================================

/**
 * SqlCompiler - compiles Query to DuckDB SQL.
 *
 * Features:
 * - LRU cache for compiled SQL (default 100 entries)
 * - Deterministic key generation for cache hits
 * - Configurable quote style and dialect
 * - Implements IDisposable for proper cleanup
 *
 * @example
 * const compiler = new SqlCompiler();
 *
 * const result = compiler.compile({
 *   dimensions: [{ member: 'users.country' }],
 *   measures: [{ member: 'orders.amount', aggregation: 'sum', alias: 'total' }],
 *   joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }],
 *   filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
 * });
 *
 * // result.sql:
 * // SELECT "users"."country" AS "country", SUM("orders"."amount") AS "total"
 * // FROM "orders"
 * // INNER JOIN "users" ON "orders"."user_id" = "users"."id"
 * // WHERE "users"."status" = 'active'
 * // GROUP BY "users"."country"
 *
 * // Cleanup when done
 * compiler.dispose();
 */
export class SqlCompiler implements IDisposable {
  private readonly config: ResolvedConfig;
  private readonly cache: SqlCompilationCache;
  private _isDisposed = false;

  constructor(config?: SqlCompilerConfig & { cacheSize?: number }) {
    this.config = {
      quoteStyle: config?.quoteStyle ?? DEFAULT_COMPILER_CONFIG.quoteStyle,
      dialect: config?.dialect ?? DEFAULT_COMPILER_CONFIG.dialect,
      includeComments: config?.includeComments ?? DEFAULT_COMPILER_CONFIG.includeComments,
      prettyPrint: config?.prettyPrint ?? DEFAULT_COMPILER_CONFIG.prettyPrint,
      defaultSchema: config?.defaultSchema ?? DEFAULT_COMPILER_CONFIG.defaultSchema,
    };
    this.cache = new SqlCompilationCache(config?.cacheSize ?? DEFAULT_CACHE_SIZE);
  }

  /**
   * Check if the compiler is disposed.
   */
  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Dispose of resources (clear cache).
   */
  dispose(): void {
    if (this._isDisposed) return;
    this._isDisposed = true;
    this.cache.clear();
  }

  /**
   * Ensure the compiler is not disposed before use.
   */
  private ensureNotDisposed(): void {
    if (this._isDisposed) {
      throw new DisposedError('SqlCompiler');
    }
  }

  /**
   * Generate a deterministic cache key for a query and options.
   *
   * Uses hashPayloadSync from foundation-utils for efficient,
   * deterministic hashing with sorted object keys.
   */
  private generateCacheKey(query: Query, options?: CompileOptions): string {
    return hashPayloadSync({ query, options });
  }

  /**
   * Clear the compilation cache.
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Get cache statistics.
   */
  getCacheStats(): { size: number; maxSize: number } {
    return this.cache.getStats();
  }

  /**
   * Compile a Query to SQL.
   *
   * Uses LRU cache to avoid re-compilation of identical queries.
   *
   * @param query - The query to compile
   * @param options - Compilation options
   * @returns Compilation result with SQL and metadata
   */
  compile = (query: Query, options?: CompileOptions): CompilationResult => {
    this.ensureNotDisposed();

    // Check cache first
    const cacheKey = this.generateCacheKey(query, options);
    const cached = this.cache.get(cacheKey);
    if (cached) {
      return cached;
    }

    // Compile the query
    const result = this.compileInternal(query, options);

    // Cache the result
    this.cache.set(cacheKey, result);

    return result;
  };

  /**
   * Internal compilation logic (not cached).
   */
  private compileInternal = (query: Query, options?: CompileOptions): CompilationResult => {
    const dimensions = query.dimensions ?? [];
    const measures = query.measures ?? [];
    const filters = query.filters ?? [];
    const joins = query.joins ?? [];
    const orderBy = query.orderBy ?? [];
    const timeDimensions = query.timeDimensions ?? [];

    // Determine primary table from first dimension, measure, or time dimension
    const primaryTable =
      options?.primaryTable ??
      (dimensions[0] ? parseMemberRef(dimensions[0].member)?.table : undefined) ??
      (measures[0] ? parseMemberRef(measures[0].member)?.table : undefined) ??
      (timeDimensions[0] ? parseMemberRef(timeDimensions[0].dimension)?.table : undefined);

    if (!primaryTable) {
      throw new QueryCompilationError('Cannot determine primary table from query');
    }

    // Collect all tables
    const tables = new Set<string>([primaryTable]);
    for (const dim of dimensions) {
      const parsed = parseMemberRef(dim.member);
      if (parsed) tables.add(parsed.table);
    }
    for (const measure of measures) {
      const parsed = parseMemberRef(measure.member);
      if (parsed) tables.add(parsed.table);
    }
    for (const join of joins) {
      const leftParsed = parseMemberRef(join.left);
      const rightParsed = parseMemberRef(join.right);
      if (leftParsed) tables.add(leftParsed.table);
      if (rightParsed) tables.add(rightParsed.table);
    }
    for (const timeDim of timeDimensions) {
      const parsed = parseMemberRef(timeDim.dimension);
      if (parsed) tables.add(parsed.table);
    }

    // Build SELECT clause
    const selectParts: string[] = [];

    for (const dim of dimensions) {
      selectParts.push(compileDimensionSelect(dim));
    }

    // Add time dimension SELECT expressions (DATE_TRUNC)
    for (const timeDim of timeDimensions) {
      if (timeDim.granularity) {
        selectParts.push(compileTimeDimensionSelect(timeDim, timeDim.granularity));
      }
    }

    for (const measure of measures) {
      selectParts.push(compileMeasureSelect(measure));
    }

    // If no dimensions, time dimensions, or measures, select all from primary table
    if (selectParts.length === 0) {
      selectParts.push(`${quoteIdentifier(primaryTable)}.*`);
    }

    const selectClause = `SELECT ${selectParts.join(', ')}`;

    // Build FROM clause
    const fromClause = `FROM ${quoteIdentifier(primaryTable)}`;

    // Build JOIN clauses
    const joinClauses = compileJoinClauses(joins, primaryTable);

    // Build WHERE clause - combine explicit filters with time dimension date range filters
    const allWhereConditions: string[] = [];

    if (filters.length > 0) {
      const conditions = filters.map((f) => compileFilterExpression(f));
      allWhereConditions.push(...conditions);
    }

    // Add time dimension date range filters to WHERE clause
    for (const timeDim of timeDimensions) {
      if (timeDim.dateRange) {
        const timeDimFilter = compileTimeDimensionFilter(timeDim, timeDim.dateRange);
        if (timeDimFilter) {
          allWhereConditions.push(timeDimFilter);
        }
      }
    }

    const whereClause =
      allWhereConditions.length > 0 ? `WHERE ${allWhereConditions.join(' AND ')}` : '';

    // Build GROUP BY clause (required if we have dimensions/time dimensions with measures)
    const hasAggregations = measures.length > 0;
    const groupByParts: string[] = [];

    if (hasAggregations) {
      // Add regular dimensions to GROUP BY
      for (const dim of dimensions) {
        groupByParts.push(quoteMemberRef(dim.member));
      }

      // Add time dimension DATE_TRUNC expressions to GROUP BY
      for (const timeDim of timeDimensions) {
        if (timeDim.granularity) {
          const truncUnit = getDateTruncUnit(timeDim.granularity);
          const memberRef = quoteMemberRef(timeDim.dimension);
          groupByParts.push(`DATE_TRUNC('${truncUnit}', ${memberRef})`);
        }
      }
    }

    const groupByClause = groupByParts.length > 0 ? `GROUP BY ${groupByParts.join(', ')}` : '';

    // Build ORDER BY clause
    const orderByClause = compileOrderByClause(orderBy);

    // Build LIMIT/OFFSET clauses
    let limitClause = '';
    if (query.limit !== undefined) {
      limitClause = `LIMIT ${query.limit}`;
    }

    let offsetClause = '';
    if (query.offset !== undefined && query.offset > 0) {
      offsetClause = `OFFSET ${query.offset}`;
    }

    // Combine all parts
    const sqlParts = [
      selectClause,
      fromClause,
      joinClauses,
      whereClause,
      groupByClause,
      orderByClause,
      limitClause,
      offsetClause,
    ].filter(Boolean);

    const rawSql = sqlParts.join('\n');
    const sql = options?.pretty || this.config.prettyPrint ? formatSql(rawSql, true) : rawSql;

    return {
      sql,
      tables: Array.from(tables),
      hasAggregations,
      hasJoins: joins.length > 0,
    };
  };

  /**
   * Compile a simple count query.
   */
  compileCount = (tableName: string): string => {
    return `SELECT COUNT(*) AS count FROM ${quoteIdentifier(tableName)}`;
  };

  /**
   * Compile a simple select all query.
   */
  compileSelectAll = (tableName: string, limit?: number, offset?: number): string => {
    let sql = `SELECT * FROM ${quoteIdentifier(tableName)}`;
    if (limit !== undefined) {
      sql += ` LIMIT ${limit}`;
    }
    if (offset !== undefined && offset > 0) {
      sql += ` OFFSET ${offset}`;
    }
    return sql;
  };

  /**
   * Get the compiler configuration.
   */
  getConfig = (): ResolvedConfig => ({ ...this.config });
}

// =============================================================================
// FACTORY
// =============================================================================

/**
 * Create a new SqlCompiler instance.
 */
export const createSqlCompiler = (config?: SqlCompilerConfig): SqlCompiler => {
  return new SqlCompiler(config);
};

// =============================================================================
// SINGLETON FACTORY
// =============================================================================

/**
 * Singleton factory for SqlCompiler.
 *
 * Use this when you need a shared SqlCompiler instance across the application.
 * The instance will be created once and reused for all subsequent calls.
 *
 * @example
 * ```typescript
 * // Get the singleton instance
 * const compiler = getSqlCompiler();
 *
 * // Compile queries
 * const result = compiler.compile(query);
 *
 * // Reset for testing
 * await resetSqlCompiler();
 * ```
 */
const sqlCompilerFactory = createSingletonFactory<SqlCompiler, SqlCompilerConfig>(
  (config) => new SqlCompiler(config),
  {
    name: 'SqlCompiler',
    warnOnConfigOverride: true,
    onDispose: (instance) => {
      if (instance instanceof SqlCompiler) {
        instance.dispose();
      }
    },
    defaultConfig: {},
  },
);

/**
 * Get the singleton SqlCompiler instance.
 */
export const getSqlCompiler = (config?: SqlCompilerConfig): SqlCompiler => {
  return sqlCompilerFactory.getInstance(config);
};

/**
 * Reset the singleton SqlCompiler instance (for testing).
 */
export const resetSqlCompiler = async (): Promise<void> => {
  await sqlCompilerFactory.reset();
};

/**
 * Check if a SqlCompiler singleton instance exists.
 */
export const hasSqlCompilerInstance = (): boolean => {
  return sqlCompilerFactory.hasInstance();
};
