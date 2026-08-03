/**
 * Empty constant references
 *
 * Provides stable empty array and object references to prevent unnecessary re-renders
 * in React components and avoid creating new objects on each render.
 *
 * @module constants/empty
 */

/**
 * Stable empty array reference.
 *
 * Use this instead of `[]` in default props, useMemo dependencies, or anywhere
 * a stable reference is needed to prevent re-renders.
 *
 * @example
 * ```typescript
 * // In a React component
 * const MyComponent = ({ items = EMPTY_ARRAY }: { items?: ReadonlyArray<string> }) => {
 *   // items will always be the same reference if not provided
 * };
 *
 * // In useMemo or useCallback
 * const result = useMemo(() => doSomething(items), [items]); // Won't re-run if items is EMPTY_ARRAY
 * ```
 */
export const EMPTY_ARRAY: ReadonlyArray<never> = Object.freeze([]);

/**
 * Stable empty object reference.
 *
 * Use this instead of `{}` in default props, useMemo dependencies, or anywhere
 * a stable reference is needed to prevent re-renders.
 *
 * @example
 * ```typescript
 * // In a React component
 * const MyComponent = ({ config = EMPTY_OBJECT }: { config?: Readonly<Record<string, never>> }) => {
 *   // config will always be the same reference if not provided
 * };
 * ```
 */
export const EMPTY_OBJECT: Readonly<Record<string, never>> = Object.freeze({});

/**
 * Stable empty Map reference.
 *
 * Use this instead of `new Map()` when a stable empty Map reference is needed.
 *
 * Note: This Map is frozen and will throw if modifications are attempted.
 *
 * @example
 * ```typescript
 * const MyComponent = ({ mapping = EMPTY_MAP }: { mapping?: ReadonlyMap<string, string> }) => {
 *   // mapping will always be the same reference if not provided
 * };
 * ```
 */
export const EMPTY_MAP: ReadonlyMap<never, never> = Object.freeze(new Map<never, never>());

/**
 * Stable empty Set reference.
 *
 * Use this instead of `new Set()` when a stable empty Set reference is needed.
 *
 * Note: This Set is frozen and will throw if modifications are attempted.
 *
 * @example
 * ```typescript
 * const MyComponent = ({ selected = EMPTY_SET }: { selected?: ReadonlySet<string> }) => {
 *   // selected will always be the same reference if not provided
 * };
 * ```
 */
export const EMPTY_SET: ReadonlySet<never> = Object.freeze(new Set<never>());
