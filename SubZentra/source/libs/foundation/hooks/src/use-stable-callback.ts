/**
 * useStableCallback - Create a callback that's stable across renders
 * but always calls the latest version
 * @module use-stable-callback
 */
import { useCallback, useLayoutEffect, useRef } from 'react';

/**
 * Creates a stable callback reference that can be passed to effects
 * without causing re-runs, while still having access to latest closure.
 *
 * Similar to useCallbackRef but handles undefined callbacks and uses
 * useLayoutEffect for synchronous updates.
 *
 * @param callback - The callback function (can be undefined)
 * @returns A stable callback that calls the latest version, or undefined
 *
 * @example
 * ```tsx
 * const stableOnSuccess = useStableCallback(onSuccess);
 *
 * useEffect(() => {
 *   if (data) {
 *     stableOnSuccess?.(data);
 *   }
 * }, [data]); // onSuccess not in deps, won't cause re-runs
 * ```
 */
export function useStableCallback<T extends (...args: never[]) => unknown>(
  callback: T | undefined,
): T | undefined {
  const callbackRef = useRef(callback);

  useLayoutEffect(() => {
    callbackRef.current = callback;
  });

  const stableCallback = useCallback(
    (...args: Parameters<T>) => callbackRef.current?.(...args),
    [],
  ) as T;

  // Return undefined if callback is undefined to preserve the same semantics
  return callback === undefined ? undefined : stableCallback;
}
