/**
 * Get current page URL
 * @module url/get-current-page-url
 */

import { isBrowser } from '../browser';
import { sanitizeUrl } from './sanitize-url';
import type { URLSanitizationOptions } from './types';

/**
 * Get current page URL (sanitized)
 * @param options - Sanitization options
 * @returns Sanitized current page URL or empty string if not in browser
 */
export const getCurrentPageUrl = (options?: Partial<URLSanitizationOptions>): string => {
  if (!isBrowser()) {
    return '';
  }
  return sanitizeUrl(window.location.href, options);
};
