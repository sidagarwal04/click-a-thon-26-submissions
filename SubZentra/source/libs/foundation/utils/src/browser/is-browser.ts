/**
 * Check if running in browser environment
 * @module browser/is-browser
 */

/**
 * Check if running in browser environment
 * @returns true if window and document are defined
 */
export const isBrowser = (): boolean =>
  typeof window !== 'undefined' && typeof document !== 'undefined';
