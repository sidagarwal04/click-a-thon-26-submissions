/**
 * Extract route from URL
 * @module url/extract-route
 */

import { isBrowser } from '../browser';

/**
 * Extract route from URL (replaces dynamic segments with placeholders)
 * @param url - URL to extract route from
 * @returns Pathname with dynamic segments replaced by {id}
 */
export const extractRoute = (url: string): string => {
  try {
    const baseUrl = isBrowser() ? window.location.origin : undefined;
    const parsed = new URL(url, baseUrl);
    let pathname = parsed.pathname;

    const patterns = [
      // UUIDs
      /\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,
      // Numeric IDs
      /\/\d+(?=\/|$)/g,
      // MongoDB ObjectIds
      /\/[0-9a-f]{24}/gi,
      // Generic alphanumeric IDs (at least 8 chars)
      /\/[a-zA-Z0-9_-]{8,}(?=\/|$)/g,
    ];

    for (const pattern of patterns) {
      pathname = pathname.replace(pattern, '/{id}');
    }

    return pathname;
  } catch {
    return url;
  }
};
