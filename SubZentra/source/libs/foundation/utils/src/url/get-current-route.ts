/**
 * Get current route
 * @module url/get-current-route
 */

import { isBrowser } from '../browser';

/**
 * Get current route/pathname
 * @returns Current pathname or empty string if not in browser
 */
export const getCurrentRoute = (): string => {
  if (!isBrowser()) {
    return '';
  }
  return window.location.pathname;
};
