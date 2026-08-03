import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { shouldPropagateTraceContext } from './should-propagate-trace-context';

describe('shouldPropagateTraceContext', () => {
  const originalWindow = global.window;

  beforeEach(() => {
    // Mock window.location
    global.window = {
      location: {
        origin: 'https://example.com',
        href: 'https://example.com/page',
      },
    } as Window & typeof globalThis;
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  it('should return true for same origin when no allowed domains', () => {
    const result = shouldPropagateTraceContext('https://example.com/api/data', []);
    expect(result).toBe(true);
  });

  it('should return false for different origin when no allowed domains', () => {
    const result = shouldPropagateTraceContext('https://other.com/api', []);
    expect(result).toBe(false);
  });

  it('should return true for exact domain match', () => {
    const result = shouldPropagateTraceContext('https://api.example.com/data', ['api.example.com']);
    expect(result).toBe(true);
  });

  it('should return false for non-matching domain', () => {
    const result = shouldPropagateTraceContext('https://other.com/api', ['api.example.com']);
    expect(result).toBe(false);
  });

  it('should match wildcard domain', () => {
    const result = shouldPropagateTraceContext('https://api.example.com/data', ['*.example.com']);
    expect(result).toBe(true);
  });

  it('should match nested subdomain with wildcard', () => {
    const result = shouldPropagateTraceContext('https://api.v2.example.com/data', [
      '*.example.com',
    ]);
    expect(result).toBe(true);
  });

  it('should match base domain with wildcard', () => {
    const result = shouldPropagateTraceContext('https://example.com/data', ['*.example.com']);
    expect(result).toBe(true);
  });

  it('should not match different base domain with wildcard', () => {
    const result = shouldPropagateTraceContext('https://notexample.com/data', ['*.example.com']);
    expect(result).toBe(false);
  });

  it('should check multiple allowed domains', () => {
    const allowedDomains = ['api.example.com', '*.internal.com'];
    expect(shouldPropagateTraceContext('https://api.example.com/data', allowedDomains)).toBe(true);
    expect(shouldPropagateTraceContext('https://service.internal.com/data', allowedDomains)).toBe(
      true,
    );
    expect(shouldPropagateTraceContext('https://other.com/data', allowedDomains)).toBe(false);
  });

  it('should return false for invalid URL', () => {
    // @ts-expect-error - testing undefined case
    delete global.window;
    const result = shouldPropagateTraceContext('not-a-valid-url', ['example.com']);
    expect(result).toBe(false);
  });
});
