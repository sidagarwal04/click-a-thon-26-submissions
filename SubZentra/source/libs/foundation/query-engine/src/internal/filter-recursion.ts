/**
 * Shared recursive traversal helpers for filter expression trees.
 *
 * @module internal/filter-recursion
 */

import type { FilterCondition, FilterExpression } from '../types/filter';
import { isFilterAndGroup, isFilterCondition, isFilterOrGroup } from '../types/filter';

/**
 * Group operator kind for logical filter groups.
 */
export const FILTER_GROUP_KINDS = {
  AND: 'and',
  OR: 'or',
} as const;

export type FilterGroupKind = (typeof FILTER_GROUP_KINDS)[keyof typeof FILTER_GROUP_KINDS];

/**
 * Mapper callbacks for `mapFilterExpression`.
 */
export interface FilterExpressionMapper<TResult> {
  readonly onCondition: (condition: FilterCondition, depth: number) => TResult;
  readonly onAndGroup: (children: ReadonlyArray<TResult>, depth: number) => TResult;
  readonly onOrGroup: (children: ReadonlyArray<TResult>, depth: number) => TResult;
}

/**
 * Recursively map a filter expression tree into a single result value.
 */
export const mapFilterExpression = <TResult>(
  expression: FilterExpression,
  mapper: FilterExpressionMapper<TResult>,
  depth = 0,
): TResult => {
  if (isFilterCondition(expression)) {
    return mapper.onCondition(expression, depth);
  }

  if (isFilterAndGroup(expression)) {
    const children = expression.and.map((child) => mapFilterExpression(child, mapper, depth + 1));
    return mapper.onAndGroup(children, depth);
  }

  if (isFilterOrGroup(expression)) {
    const children = expression.or.map((child) => mapFilterExpression(child, mapper, depth + 1));
    return mapper.onOrGroup(children, depth);
  }

  return mapper.onAndGroup([], depth);
};
