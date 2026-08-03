/**
 * Check if URL is same origin
 * @module url/is-same-origin
 */

import { isBrowser } from '../browser';

/**
 * Check if URL is same origin as current page
 * @param url - URL to check
 * @returns true if same origin, false otherwise
 */
export const isSameOrigin = (url: string): boolean => {
  if (!isBrowser()) {
    return false;
  }

  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin;
  } catch {
    return false;
  }
};
