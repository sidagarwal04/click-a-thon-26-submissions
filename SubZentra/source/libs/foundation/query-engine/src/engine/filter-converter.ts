/**
 * Filter Converter
 *
 * Converts Query filters to simple args for data-layer hooks (useDLGetList).
 * Only converts simple equality filters that can be passed to HTTP APIs.
 * Complex filters (comparison, string operators, groups) require DuckDB.
 *
 * This is a lightweight replacement for the deleted ApiParamsConverter.
 *
 * @module engine/filter-converter
 */

import type { FilterExpression } from '../types/filter';
import { isFilterCondition } from '../types/filter';
import type { Query } from '../types/query';
import { parseMemberRef } from '../utils/member-ref';

// =============================================================================
// TYPES
// =============================================================================

/**
 * Converted args for data-layer hooks.
 * Contains pagination and simple equality filters.
 */
export interface ConvertedArgs {
  readonly [key: string]: unknown;
}

// =============================================================================
// FILTER CONVERSION
// =============================================================================

/**
 * Check if a filter can be converted to a simple API argument.
 * Only equality filters with a single value can be converted.
 *
 * @param filter - The filter expression to check
 * @returns True if the filter can be converted
 */
const isConvertibleFilter = (filter: FilterExpression): boolean => {
  if (!isFilterCondition(filter)) {
    return false;
  }
  // Only equality with exactly one value
  return filter.operator === 'equals' && (filter.values?.length ?? 0) === 1;
};

/**
 * Convert Query filters to simple args for useDLGetList.
 *
 * This function extracts:
 * - Pagination (limit, offset)
 * - Simple equality filters (field = value)
 *
 * Complex filters (comparisons, LIKE, IN, groups) are NOT converted.
 * Queries with complex filters should use the DuckDB path.
 *
 * @param query - The Query object to convert
 * @returns Args object for an API-backed query
 *
 * @example
 * ```typescript
 * const query: Query = {
 *   dimensions: [{ member: 'users.name' }],
 *   filters: [
 *     { member: 'users.status', operator: 'equals', values: ['active'] },
 *     { member: 'users.role', operator: 'equals', values: ['admin'] },
 *   ],
 *   limit: 10,
 * };
 *
 * const args = convertFiltersToArgs(query);
 * // { status: 'active', role: 'admin', limit: 10 }
 * ```
 */
export const convertFiltersToArgs = (query: Query): ConvertedArgs => {
  const args: Record<string, unknown> = {};

  // Add pagination
  if (query.limit !== undefined) {
    args.limit = query.limit;
  }
  if (query.offset !== undefined) {
    args.offset = query.offset;
  }

  // Convert simple equality filters
  if (query.filters) {
    for (const filter of query.filters) {
      if (isConvertibleFilter(filter) && isFilterCondition(filter)) {
        const parsed = parseMemberRef(filter.member);
        if (parsed && filter.values?.length === 1) {
          // Use the column name as the arg key
          args[parsed.column] = filter.values[0];
        }
      }
    }
  }

  return args;
};

/**
 * Check if a query has any complex filters that cannot be converted to API args.
 * Queries with complex filters should use the DuckDB path.
 *
 * @param query - The Query object to check
 * @returns True if the query has complex filters
 */
export const hasComplexFilters = (query: Query): boolean => {
  if (!query.filters || query.filters.length === 0) {
    return false;
  }

  for (const filter of query.filters) {
    if (!isConvertibleFilter(filter)) {
      return true;
    }
  }

  return false;
};

/**
 * Count the number of convertible filters in a query.
 *
 * @param query - The Query object to analyze
 * @returns Number of filters that can be converted to API args
 */
export const countConvertibleFilters = (query: Query): number => {
  if (!query.filters) {
    return 0;
  }

  return query.filters.filter(isConvertibleFilter).length;
};
