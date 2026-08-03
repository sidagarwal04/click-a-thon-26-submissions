/**
 * useMountedRef - Track component mounted state
 * @module use-mounted-ref
 */
import { useEffect, useRef } from 'react';

/**
 * Hook to track if a component is mounted.
 * Use this to safely update state in async callbacks.
 *
 * @returns A ref that is true when mounted, false when unmounted
 *
 * @example
 * ```tsx
 * const mountedRef = useMountedRef();
 *
 * useEffect(() => {
 *   fetchData().then(data => {
 *     if (mountedRef.current) {
 *       setData(data);
 *     }
 *   });
 * }, []);
 * ```
 */
export function useMountedRef(): React.RefObject<boolean> {
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return mountedRef;
}
