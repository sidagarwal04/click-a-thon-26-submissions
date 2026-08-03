/**
 * useAbortController - Manage AbortController lifecycle
 * @module use-abort-controller
 */
import { useCallback, useEffect, useRef } from 'react';

/**
 * Result of the useAbortController hook
 */
export interface UseAbortControllerResult {
  /** Get the current AbortSignal */
  getSignal: () => AbortSignal;
  /** Create a new AbortController (aborts the previous one) */
  reset: () => AbortController;
  /** Abort the current controller */
  abort: () => void;
}

/**
 * Hook to manage AbortController lifecycle with automatic cleanup.
 *
 * @returns Object with methods to manage the AbortController
 *
 * @example
 * ```tsx
 * const { getSignal, reset, abort } = useAbortController();
 *
 * const fetchData = async () => {
 *   const controller = reset(); // Aborts previous, creates new
 *   const response = await fetch(url, { signal: controller.signal });
 *   // ...
 * };
 *
 * // Automatically aborts on unmount
 * ```
 */
export function useAbortController(): UseAbortControllerResult {
  const controllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  const getSignal = useCallback(() => {
    if (!controllerRef.current) {
      controllerRef.current = new AbortController();
    }
    return controllerRef.current.signal;
  }, []);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = new AbortController();
    return controllerRef.current;
  }, []);

  const abort = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  return { getSignal, reset, abort };
}
