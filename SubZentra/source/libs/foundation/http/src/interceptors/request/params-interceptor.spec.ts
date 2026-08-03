/**
 * Params Interceptor Tests
 *
 * Tests for query parameter cleaning and array serialization.
 */

import type { InternalAxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createParamsInterceptor, createParamsSerializer } from './params-interceptor';

// =============================================================================
// Helpers
// =============================================================================

const makeConfig = (params?: Record<string, unknown>): InternalAxiosRequestConfig =>
  ({ params, headers: {} } as unknown as InternalAxiosRequestConfig);

// =============================================================================
// createParamsInterceptor
// =============================================================================

describe('createParamsInterceptor', () => {
  it('should remove null and undefined values by default', () => {
    const interceptor = createParamsInterceptor();
    const config = makeConfig({ a: 1, b: null, c: undefined, d: 'hello' });
    const result = interceptor(config);
    expect(result.params).toEqual({ a: 1, d: 'hello' });
  });

  it('should return undefined params when all values are nullish', () => {
    const interceptor = createParamsInterceptor();
    const config = makeConfig({ a: null, b: undefined });
    const result = interceptor(config);
    expect(result.params).toBeUndefined();
  });

  it('should pass through when removeNullish is false', () => {
    const interceptor = createParamsInterceptor({ removeNullish: false });
    const config = makeConfig({ a: 1, b: null });
    const result = interceptor(config);
    expect(result.params).toEqual({ a: 1, b: null });
  });

  it('should pass through when no params exist', () => {
    const interceptor = createParamsInterceptor();
    const config = makeConfig();
    const result = interceptor(config);
    expect(result.params).toBeUndefined();
  });

  it('should keep zero and empty string values', () => {
    const interceptor = createParamsInterceptor();
    const config = makeConfig({ a: 0, b: '', c: false });
    const result = interceptor(config);
    expect(result.params).toEqual({ a: 0, b: '', c: false });
  });
});

// =============================================================================
// createParamsSerializer
// =============================================================================

describe('createParamsSerializer', () => {
  describe('basic serialization', () => {
    it('should serialize simple key-value pairs', () => {
      const serializer = createParamsSerializer({ removeNullish: true });
      const result = serializer({ name: 'test', page: 1 });
      expect(result).toContain('name=test');
      expect(result).toContain('page=1');
    });

    it('should encode special characters', () => {
      const serializer = createParamsSerializer({ removeNullish: true });
      const result = serializer({ q: 'hello world' });
      expect(result).toBe('q=hello%20world');
    });

    it('should skip null/undefined when removeNullish is true', () => {
      const serializer = createParamsSerializer({ removeNullish: true });
      const result = serializer({ a: 'yes', b: null, c: undefined });
      expect(result).toBe('a=yes');
    });

    it('should serialize null/undefined as empty when removeNullish is false', () => {
      const serializer = createParamsSerializer({ removeNullish: false });
      const result = serializer({ a: null });
      expect(result).toBe('a=');
    });

    it('should serialize objects as JSON', () => {
      const serializer = createParamsSerializer({ removeNullish: true });
      const result = serializer({ filter: { status: 'active' } });
      expect(result).toContain('filter=');
      expect(decodeURIComponent(result)).toContain('{"status":"active"}');
    });
  });

  describe('array formats', () => {
    it('should use repeat format by default', () => {
      const serializer = createParamsSerializer({ removeNullish: true });
      const result = serializer({ ids: [1, 2, 3] });
      expect(result).toBe('ids=1&ids=2&ids=3');
    });

    it('should support brackets format', () => {
      const serializer = createParamsSerializer({ removeNullish: true, arrayFormat: 'brackets' });
      const result = serializer({ ids: [1, 2] });
      // Brackets [] are added literally (not URI-encoded) after the encoded key
      expect(result).toBe('ids[]=1&ids[]=2');
    });

    it('should support indices format', () => {
      const serializer = createParamsSerializer({ removeNullish: true, arrayFormat: 'indices' });
      const result = serializer({ ids: [1, 2] });
      // Index brackets are added literally after the encoded key
      expect(result).toBe('ids[0]=1&ids[1]=2');
    });

    it('should support comma format', () => {
      const serializer = createParamsSerializer({ removeNullish: true, arrayFormat: 'comma' });
      const result = serializer({ ids: [1, 2, 3] });
      // Comma-separated values joined with literal commas
      expect(result).toBe('ids=1,2,3');
    });

    it('should skip empty arrays', () => {
      const serializer = createParamsSerializer({ removeNullish: true });
      const result = serializer({ ids: [], name: 'test' });
      expect(result).toBe('name=test');
    });
  });
});
