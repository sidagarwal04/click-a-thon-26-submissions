/**
 * Table Extractor
 *
 * Extracts table names from query members (dimensions, measures, filters, joins).
 * Tables are NEVER specified explicitly - they are inferred from member references.
 *
 * @example
 * // Query:
 * {
 *   dimensions: [{ member: 'users.name' }],
 *   measures: [{ member: 'orders.amount', aggregation: 'sum' }],
 *   filters: [{ member: 'users.status', operator: 'equals', values: ['active'] }],
 *   joins: [{ left: 'orders.user_id', right: 'users.id', type: 'inner' }]
 * }
 *
 * // Extracted tables: ['users', 'orders']
 *
 * @module engine/table-extractor
 */

import { createSingletonFactory } from '@open-zentra/foundation-utils';

import { mapFilterExpression } from '../internal/filter-recursion';
import type { DimensionSpec } from '../types/dimension';
import type { FilterCondition, FilterExpression } from '../types/filter';
import type { JoinSpec } from '../types/join';
import type { MeasureSpec } from '../types/measure';
import type { OrderBySpec } from '../types/order';
import type { Query } from '../types/query';
import { parseMemberRef } from '../utils/member-ref';

// =============================================================================
// MEMBER PARSING
// =============================================================================

/**
 * Extract table name from a member reference.
 *
 * @param member - Member reference in 'table.column' format
 * @returns Table name or null if invalid format
 */
const extractTableFromMember = (member: string): string | null => {
  const parsed = parseMemberRef(member);
  return parsed?.table ?? null;
};

// =============================================================================
// FILTER EXTRACTION
// =============================================================================

/**
 * Extract tables from a filter condition.
 */
const extractTablesFromCondition = (condition: FilterCondition): string[] => {
  const table = extractTableFromMember(condition.member);
  return table ? [table] : [];
};

const extractTablesFromFilterExpression = (expression: FilterExpression): string[] =>
  mapFilterExpression(expression, {
    onCondition: extractTablesFromCondition,
    onAndGroup: (children) => children.flat(),
    onOrGroup: (children) => children.flat(),
  });

// =============================================================================
// TABLE EXTRACTOR CLASS
// =============================================================================

/**
 * Result of table extraction.
 */
export interface TableExtractionResult {
  /**
   * All unique tables found in the query.
   */
  readonly tables: ReadonlyArray<string>;

  /**
   * Primary table (first non-null table found).
   * This is typically the main table being queried.
   */
  readonly primaryTable: string | null;

  /**
   * Tables found in dimensions.
   */
  readonly fromDimensions: ReadonlyArray<string>;

  /**
   * Tables found in measures.
   */
  readonly fromMeasures: ReadonlyArray<string>;

  /**
   * Tables found in filters.
   */
  readonly fromFilters: ReadonlyArray<string>;

  /**
   * Tables found in joins.
   */
  readonly fromJoins: ReadonlyArray<string>;

  /**
   * Tables found in order by.
   */
  readonly fromOrderBy: ReadonlyArray<string>;

  /**
   * Whether extraction found any tables.
   */
  readonly hasTable: boolean;

  /**
   * Whether query involves multiple tables (suggests joins needed).
   */
  readonly hasMultipleTables: boolean;
}

/**
 * TableExtractor - extracts table names from query members.
 *
 * Tables are inferred from member references in:
 * - dimensions: { member: 'users.name' } → 'users'
 * - measures: { member: 'orders.amount', ... } → 'orders'
 * - filters: { member: 'products.status', ... } → 'products'
 * - joins: { left: 'orders.user_id', right: 'users.id' } → 'orders', 'users'
 * - orderBy: { member: 'users.created_at', ... } → 'users'
 */
export class TableExtractor {
  /**
   * Extract all unique table names from a query.
   *
   * @param query - The enterprise query
   * @returns Array of unique table names (order preserved)
   */
  extract(query: Partial<Query>): string[] {
    const result = this.extractDetailed(query);
    return [...result.tables];
  }

  /**
   * Extract detailed table information from a query.
   *
   * @param query - The enterprise query
   * @returns Detailed extraction result
   */
  extractDetailed(query: Partial<Query>): TableExtractionResult {
    const fromDimensions = this.extractFromDimensions(query.dimensions ?? []);
    const fromMeasures = this.extractFromMeasures(query.measures ?? []);
    const fromFilters = this.extractFromFilters(query.filters ?? []);
    const fromJoins = this.extractFromJoins(query.joins ?? []);
    const fromOrderBy = this.extractFromOrderBy(query.orderBy ?? []);

    // Combine all tables and deduplicate while preserving order
    const allTables = [
      ...fromDimensions,
      ...fromMeasures,
      ...fromFilters,
      ...fromJoins,
      ...fromOrderBy,
    ];

    const uniqueTables = this.deduplicatePreserveOrder(allTables);
    const primaryTable = uniqueTables[0] ?? null;

    return {
      tables: uniqueTables,
      primaryTable,
      fromDimensions: this.deduplicatePreserveOrder(fromDimensions),
      fromMeasures: this.deduplicatePreserveOrder(fromMeasures),
      fromFilters: this.deduplicatePreserveOrder(fromFilters),
      fromJoins: this.deduplicatePreserveOrder(fromJoins),
      fromOrderBy: this.deduplicatePreserveOrder(fromOrderBy),
      hasTable: uniqueTables.length > 0,
      hasMultipleTables: uniqueTables.length > 1,
    };
  }

  /**
   * Get the primary table from a query.
   * Primary table is the first table found (from dimensions first).
   */
  getPrimaryTable(query: Partial<Query>): string | null {
    const result = this.extractDetailed(query);
    return result.primaryTable;
  }

  /**
   * Check if query involves multiple tables.
   */
  hasMultipleTables(query: Partial<Query>): boolean {
    const result = this.extractDetailed(query);
    return result.hasMultipleTables;
  }

  /**
   * Extract tables from dimensions.
   */
  extractFromDimensions(dimensions: ReadonlyArray<DimensionSpec>): string[] {
    const tables: string[] = [];

    for (const dim of dimensions) {
      const table = extractTableFromMember(dim.member);
      if (table) {
        tables.push(table);
      }
    }

    return tables;
  }

  /**
   * Extract tables from measures.
   */
  extractFromMeasures(measures: ReadonlyArray<MeasureSpec>): string[] {
    const tables: string[] = [];

    for (const measure of measures) {
      const table = extractTableFromMember(measure.member);
      if (table) {
        tables.push(table);
      }

      // Also check filter on measure
      if (measure.filter) {
        const filterTable = extractTableFromMember(measure.filter.member);
        if (filterTable) {
          tables.push(filterTable);
        }
      }
    }

    return tables;
  }

  /**
   * Extract tables from filters.
   */
  extractFromFilters(filters: ReadonlyArray<FilterExpression>): string[] {
    const tables: string[] = [];

    for (const filter of filters) {
      tables.push(...extractTablesFromFilterExpression(filter));
    }

    return tables;
  }

  /**
   * Extract tables from joins.
   */
  extractFromJoins(joins: ReadonlyArray<JoinSpec>): string[] {
    const tables: string[] = [];

    for (const join of joins) {
      const leftTable = extractTableFromMember(join.left);
      const rightTable = extractTableFromMember(join.right);

      if (leftTable) {
        tables.push(leftTable);
      }
      if (rightTable) {
        tables.push(rightTable);
      }

      // Also check additional conditions
      if (join.additionalConditions) {
        for (const cond of join.additionalConditions) {
          const condLeftTable = extractTableFromMember(cond.left);
          const condRightTable = extractTableFromMember(cond.right);
          if (condLeftTable) {
            tables.push(condLeftTable);
          }
          if (condRightTable) {
            tables.push(condRightTable);
          }
        }
      }
    }

    return tables;
  }

  /**
   * Extract tables from order by.
   */
  extractFromOrderBy(orderBy: ReadonlyArray<OrderBySpec>): string[] {
    const tables: string[] = [];

    for (const order of orderBy) {
      const table = extractTableFromMember(order.member);
      if (table) {
        tables.push(table);
      }
    }

    return tables;
  }

  /**
   * Deduplicate array while preserving order.
   */
  private deduplicatePreserveOrder(arr: string[]): string[] {
    const seen = new Set<string>();
    const result: string[] = [];

    for (const item of arr) {
      if (!seen.has(item)) {
        seen.add(item);
        result.push(item);
      }
    }

    return result;
  }
}

// =============================================================================
// FACTORY
// =============================================================================

/**
 * Create a new TableExtractor instance.
 */
export const createTableExtractor = (): TableExtractor => {
  return new TableExtractor();
};

// =============================================================================
// SINGLETON FACTORY
// =============================================================================

/**
 * Singleton factory for TableExtractor.
 *
 * TableExtractor is stateless, so a singleton is appropriate.
 *
 * @example
 * ```typescript
 * // Get the singleton instance
 * const extractor = getTableExtractor();
 *
 * // Extract tables
 * const tables = extractor.extract(query);
 * ```
 */
const tableExtractorFactory = createSingletonFactory<TableExtractor, void>(
  () => new TableExtractor(),
  {
    name: 'TableExtractor',
    warnOnConfigOverride: false, // No config
  },
);

/**
 * Get the singleton TableExtractor instance.
 */
export const getTableExtractor = (): TableExtractor => {
  return tableExtractorFactory.getInstance();
};

/**
 * Reset the singleton TableExtractor instance (for testing).
 */
export const resetTableExtractor = async (): Promise<void> => {
  await tableExtractorFactory.reset();
};

// =============================================================================
// STANDALONE UTILITIES
// =============================================================================

/**
 * Extract tables from a query (convenience function).
 * Uses the singleton TableExtractor.
 *
 * NOTE: Each standalone call creates its own `extractDetailed()` result.
 * If you need both `extractTables()` and `getPrimaryTable()` for the same
 * query, prefer calling `getTableExtractor().extractDetailed(query)` once
 * and reading `tables` / `primaryTable` from the result.
 */
export const extractTables = (query: Partial<Query>): string[] => {
  return getTableExtractor().extract(query);
};

/**
 * Get the primary table from a query (convenience function).
 * Uses the singleton TableExtractor.
 *
 * @see extractTables for note on avoiding redundant calls
 */
export const getPrimaryTable = (query: Partial<Query>): string | null => {
  return getTableExtractor().getPrimaryTable(query);
};
