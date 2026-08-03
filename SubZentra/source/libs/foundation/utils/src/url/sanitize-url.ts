/**
 * Sanitize a URL for safe logging/telemetry
 * @module url/sanitize-url
 */

import { isBrowser } from '../browser';
import { DEFAULT_SANITIZATION_OPTIONS, type URLSanitizationOptions } from './types';

/**
 * Sanitize a URL for safe logging/telemetry
 * @param url - URL to sanitize
 * @param options - Sanitization options
 * @returns Sanitized URL string
 */
export const sanitizeUrl = (url: string, options: Partial<URLSanitizationOptions> = {}): string => {
  const opts = { ...DEFAULT_SANITIZATION_OPTIONS, ...options };

  try {
    const baseUrl = isBrowser() ? window.location.origin : undefined;
    const parsed = new URL(url, baseUrl);

    if (opts.removeAuth) {
      parsed.username = '';
      parsed.password = '';
    }

    if (opts.removePort) {
      parsed.port = '';
    }

    if (opts.removeQueryParams) {
      if (opts.preserveQueryParams.length > 0) {
        const preservedParams = new URLSearchParams();
        opts.preserveQueryParams.forEach((param) => {
          const value = parsed.searchParams.get(param);
          if (value !== null) {
            preservedParams.set(param, value);
          }
        });
        parsed.search = preservedParams.toString() ? `?${preservedParams.toString()}` : '';
      } else {
        parsed.search = '';
      }
    }

    if (opts.removeHash) {
      parsed.hash = '';
    }

    let pathname = parsed.pathname;
    if (opts.maskPathPatterns.length > 0) {
      for (const pattern of opts.maskPathPatterns) {
        pathname = pathname.replace(pattern, (match) => {
          return match.replace(/\/[^/]+$/, '/{id}');
        });
      }
      parsed.pathname = pathname;
    }

    return parsed.toString();
  } catch {
    return sanitizeMalformedUrl(url);
  }
};

/**
 * Sanitize a potentially malformed URL
 */
const sanitizeMalformedUrl = (url: string): string => {
  let sanitized = url;

  // Remove potential auth in URL
  sanitized = sanitized.replace(/\/\/[^:]+:[^@]+@/, '//[REDACTED]@');

  // Remove query string if it exists
  const queryIndex = sanitized.indexOf('?');
  if (queryIndex !== -1) {
    sanitized = sanitized.substring(0, queryIndex) + '?[PARAMS_REDACTED]';
  }

  // Remove hash
  const hashIndex = sanitized.indexOf('#');
  if (hashIndex !== -1) {
    sanitized = sanitized.substring(0, hashIndex);
  }

  return sanitized;
};
