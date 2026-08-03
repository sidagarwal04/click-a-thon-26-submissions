/**
 * Error Normalizer Interceptor Tests
 *
 * Tests for converting AxiosErrors and non-2xx responses into typed HttpErrors.
 */

import type { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import {
  HttpCancelledError,
  HttpForbiddenError,
  HttpNetworkError,
  HttpNotFoundError,
  HttpRequestError,
  HttpServerError,
  HttpTimeoutError,
  HttpUnauthorizedError,
} from '../../errors/http-errors';
import { convertAxiosError, convertResponseError } from './error-normalizer';

// =============================================================================
// Helpers
// =============================================================================

const makeConfig = (
  url = '/api/test',
  method = 'get',
  timeout = 30_000,
): InternalAxiosRequestConfig =>
  ({ url, method, timeout, headers: {} } as unknown as InternalAxiosRequestConfig);

const makeAxiosError = (
  code: string | undefined,
  status?: number,
  data?: unknown,
  url = '/api/test',
  method = 'get',
): AxiosError => {
  const config = makeConfig(url, method);
  const response = status
    ? ({ status, data, config, headers: {}, statusText: '' } as AxiosResponse)
    : undefined;

  return {
    isAxiosError: true,
    name: 'AxiosError',
    message: `Request failed${status ? ` with status ${status}` : ''}`,
    code,
    config,
    response,
    toJSON: () => ({}),
  } as AxiosError;
};

const makeResponse = (
  status: number,
  data?: unknown,
  url = '/api/test',
  method = 'get',
): AxiosResponse =>
  ({
    status,
    data,
    config: makeConfig(url, method),
    headers: {},
    statusText: '',
  } as AxiosResponse);

// =============================================================================
// convertAxiosError
// =============================================================================

describe('convertAxiosError', () => {
  it('should convert cancelled error to HttpCancelledError', () => {
    const error = makeAxiosError('ERR_CANCELED');
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpCancelledError);
  });

  it('should convert timeout error to HttpTimeoutError', () => {
    const error = makeAxiosError('ECONNABORTED');
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpTimeoutError);
  });

  it('should convert ETIMEDOUT to HttpTimeoutError', () => {
    const error = makeAxiosError('ETIMEDOUT');
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpTimeoutError);
  });

  it('should convert network error to HttpNetworkError', () => {
    const error = makeAxiosError('ERR_NETWORK');
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpNetworkError);
  });

  it('should convert no-response errors to HttpNetworkError', () => {
    const error = makeAxiosError(undefined);
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpNetworkError);
  });

  it('should convert 401 response to HttpUnauthorizedError', () => {
    const error = makeAxiosError(undefined, 401);
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpUnauthorizedError);
  });

  it('should convert 403 response to HttpForbiddenError', () => {
    const error = makeAxiosError(undefined, 403);
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpForbiddenError);
  });

  it('should convert 404 response to HttpNotFoundError', () => {
    const error = makeAxiosError(undefined, 404);
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpNotFoundError);
  });

  it('should convert 500+ response to HttpServerError', () => {
    const error = makeAxiosError(undefined, 502);
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpServerError);
  });

  it('should convert other 4xx to HttpRequestError', () => {
    const error = makeAxiosError(undefined, 422);
    const result = convertAxiosError(error);
    expect(result).toBeInstanceOf(HttpRequestError);
  });

  it('should extract message from response data.message', () => {
    const error = makeAxiosError(undefined, 400, { message: 'Validation failed' });
    const result = convertAxiosError(error);
    expect(result.message).toBe('Validation failed');
  });

  it('should extract message from response data.error', () => {
    const error = makeAxiosError(undefined, 400, { error: 'Bad input' });
    const result = convertAxiosError(error);
    expect(result.message).toBe('Bad input');
  });

  it('should extract message from response data.errors array', () => {
    const error = makeAxiosError(undefined, 400, { errors: [{ message: 'Field required' }] });
    const result = convertAxiosError(error);
    expect(result.message).toBe('Field required');
  });
});

// =============================================================================
// convertResponseError
// =============================================================================

describe('convertResponseError', () => {
  it('should convert 401 response to HttpUnauthorizedError', () => {
    const result = convertResponseError(makeResponse(401));
    expect(result).toBeInstanceOf(HttpUnauthorizedError);
  });

  it('should convert 403 response to HttpForbiddenError', () => {
    const result = convertResponseError(makeResponse(403));
    expect(result).toBeInstanceOf(HttpForbiddenError);
  });

  it('should convert 404 response to HttpNotFoundError', () => {
    const result = convertResponseError(makeResponse(404));
    expect(result).toBeInstanceOf(HttpNotFoundError);
  });

  it('should convert 500 response to HttpServerError', () => {
    const result = convertResponseError(makeResponse(500));
    expect(result).toBeInstanceOf(HttpServerError);
  });

  it('should convert other 4xx to HttpRequestError', () => {
    const result = convertResponseError(makeResponse(422));
    expect(result).toBeInstanceOf(HttpRequestError);
  });

  it('should use string body as error message', () => {
    const result = convertResponseError(makeResponse(400, 'Plain text error'));
    expect(result.message).toBe('Plain text error');
  });

  it('should fall back to HTTP status in message', () => {
    const result = convertResponseError(makeResponse(418));
    expect(result.message).toContain('418');
  });

  it('should preserve url and method', () => {
    const result = convertResponseError(makeResponse(400, null, '/api/v1/items', 'post'));
    const httpError = result as HttpRequestError;
    expect(httpError.url).toBe('/api/v1/items');
    expect(httpError.method).toBe('POST');
  });
});
