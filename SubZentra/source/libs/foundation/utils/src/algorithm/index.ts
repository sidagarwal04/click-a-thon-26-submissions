/**
 * Algorithm utilities
 *
 * Common algorithms for data manipulation.
 *
 * @module algorithm
 */

// =============================================================================
// Topological Sort
// =============================================================================

/**
 * Sort items by their dependencies using topological sort (DFS-based)
 *
 * Dependencies are processed first, ensuring items appear after all their
 * dependencies in the result array. This is useful for:
 * - Determining file load order
 * - View creation order
 * - Module initialization order
 * - Any DAG (Directed Acyclic Graph) ordering
 *
 * @template T - The item type
 * @param items - Array of items to sort
 * @param getKey - Function to get unique key for an item
 * @param getDependencies - Function to get dependency keys for an item
 * @returns Sorted array with dependencies before dependents
 *
 * @example
 * ```typescript
 * interface Module {
 *   name: string;
 *   imports: string[];
 * }
 *
 * const modules: Module[] = [
 *   { name: 'app', imports: ['utils', 'api'] },
 *   { name: 'utils', imports: [] },
 *   { name: 'api', imports: ['utils'] },
 * ];
 *
 * const sorted = topologicalSort(
 *   modules,
 *   (m) => m.name,
 *   (m) => m.imports
 * );
 * // Result: [utils, api, app]
 * ```
 *
 * @example
 * ```typescript
 * // With optional dependencies
 * interface File {
 *   path: string;
 *   dependencies?: string[];
 * }
 *
 * const sorted = topologicalSort(
 *   files,
 *   (f) => f.path,
 *   (f) => f.dependencies ?? []
 * );
 * ```
 */
export const topologicalSort = <T>(
  items: readonly T[],
  getKey: (item: T) => string,
  getDependencies: (item: T) => readonly string[],
): T[] => {
  const itemMap = new Map(items.map((item) => [getKey(item), item]));
  const visited = new Set<string>();
  const result: T[] = [];

  const visit = (key: string): void => {
    if (visited.has(key)) return;
    visited.add(key);

    const item = itemMap.get(key);
    if (!item) return;

    // Visit dependencies first
    for (const dep of getDependencies(item)) {
      visit(dep);
    }

    result.push(item);
  };

  for (const item of items) {
    visit(getKey(item));
  }

  return result;
};

/**
 * Check if a graph has a cycle
 *
 * @template T - The item type
 * @param items - Array of items to check
 * @param getKey - Function to get unique key for an item
 * @param getDependencies - Function to get dependency keys for an item
 * @returns true if a cycle exists
 *
 * @example
 * ```typescript
 * const hasCycle = hasCircularDependency(
 *   modules,
 *   (m) => m.name,
 *   (m) => m.imports
 * );
 * ```
 */
export const hasCircularDependency = <T>(
  items: readonly T[],
  getKey: (item: T) => string,
  getDependencies: (item: T) => readonly string[],
): boolean => {
  const itemMap = new Map(items.map((item) => [getKey(item), item]));
  const visited = new Set<string>();
  const visiting = new Set<string>(); // Items in current DFS path

  const visit = (key: string): boolean => {
    if (visiting.has(key)) return true; // Cycle detected
    if (visited.has(key)) return false;

    visiting.add(key);

    const item = itemMap.get(key);
    if (item) {
      for (const dep of getDependencies(item)) {
        if (visit(dep)) return true;
      }
    }

    visiting.delete(key);
    visited.add(key);
    return false;
  };

  for (const item of items) {
    if (visit(getKey(item))) return true;
  }

  return false;
};
