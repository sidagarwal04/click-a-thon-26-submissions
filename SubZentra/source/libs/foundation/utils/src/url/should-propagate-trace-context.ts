/**
 * Check if trace context should be propagated
 * @module url/should-propagate-trace-context
 */

import { isBrowser } from '../browser';
import { isSameOrigin } from './is-same-origin';

/**
 * Check if URL should have trace context propagated to it
 * @param url - URL to check
 * @param allowedDomains - List of domains to allow trace propagation (supports wildcard: *.example.com)
 * @returns true if trace context should be propagated
 */
export const shouldPropagateTraceContext = (url: string, allowedDomains: string[]): boolean => {
  if (allowedDomains.length === 0) {
    return isSameOrigin(url);
  }

  try {
    const baseUrl = isBrowser() ? window.location.origin : undefined;
    const parsed = new URL(url, baseUrl);
    const hostname = parsed.hostname;

    return allowedDomains.some((domain) => {
      if (domain.startsWith('*.')) {
        const baseDomain = domain.slice(2);
        return hostname === baseDomain || hostname.endsWith(`.${baseDomain}`);
      }
      return hostname === domain;
    });
  } catch {
    return false;
  }
};
