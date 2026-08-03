/**
 * useCallbackRef - Store callback in ref to avoid dependency issues
 * @module use-callback-ref
 */
import { useCallback, useEffect, useRef } from 'react';

/**
 * Hook to create a stable callback reference.
 * The returned callback always calls the latest version of the provided callback.
 * Useful for event listeners where you don't want to re-subscribe when callback changes.
 *
 * @param callback - The callback function to stabilize
 * @returns A stable callback that always calls the latest version
 *
 * @example
 * ```tsx
 * const handleEvent = useCallbackRef((event: SyncEvent) => {
 *   // Always has access to latest state/props
 *   console.log(event, someState);
 * });
 *
 * useEffect(() => {
 *   return subscribe(handleEvent); // Won't re-subscribe when callback changes
 * }, []); // Safe to have empty deps
 * ```
 */
export function useCallbackRef<T extends (...args: never[]) => unknown>(callback: T): T {
  const callbackRef = useRef(callback);

  // Update ref on every render
  useEffect(() => {
    callbackRef.current = callback;
  });

  // Return stable callback that calls the ref
  return useCallback(
    (...args: Parameters<T>) => callbackRef.current(...args),
    [],
  ) as T;
}
