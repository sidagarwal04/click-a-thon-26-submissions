/**
 * Request Metadata Utilities
 *
 * Safe helpers for extracting normalized request URL, method, and host data
 * from Axios request configs.
 *
 * @module core/request-metadata
 */

import type { AxiosRequestConfig } from 'axios';

import { HTTP_METHOD, type HttpMethod } from '@open-zentra/foundation-data-model';

const UNKNOWN_HOST_KEY = '__unknown__';

/**
 * Normalize an HTTP method string to a known HttpMethod constant.
 */
export const normalizeHttpMethod = (method: string | undefined): HttpMethod | undefined => {
  if (!method) {
    return undefined;
  }

  const upperMethod = method.toUpperCase();
  const matchedMethod = Object.values(HTTP_METHOD).find((value) => value === upperMethod);
  return matchedMethod;
};

/**
 * Resolve a request URL to an absolute URL when possible.
 */
export const resolveRequestUrl = (
  url: string | undefined,
  baseUrl: string | undefined,
): string | undefined => {
  if (!url) {
    return undefined;
  }

  try {
    if (baseUrl) {
      return new URL(url, baseUrl).toString();
    }

    return new URL(url).toString();
  } catch {
    return url;
  }
};

/**
 * Extract a host key from request URL/baseURL.
 */
export const extractHostKey = (url: string | undefined, baseUrl: string | undefined): string => {
  const resolvedUrl = resolveRequestUrl(url, baseUrl);
  if (!resolvedUrl) {
    return UNKNOWN_HOST_KEY;
  }

  try {
    return new URL(resolvedUrl).host || UNKNOWN_HOST_KEY;
  } catch {
    return UNKNOWN_HOST_KEY;
  }
};

export interface RequestMetadata {
  readonly requestUrl?: string;
  readonly method?: HttpMethod;
  readonly hostKey: string;
}

/**
 * Build normalized metadata from a request config.
 */
export const getRequestMetadata = (
  config: Pick<AxiosRequestConfig, 'url' | 'baseURL' | 'method'>,
): RequestMetadata => {
  const requestUrl = resolveRequestUrl(config.url, config.baseURL);
  const method = normalizeHttpMethod(config.method);
  const hostKey = extractHostKey(config.url, config.baseURL);

  return {
    requestUrl,
    method,
    hostKey,
  };
};
