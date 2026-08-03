import { describe, expect, it } from 'vitest';

import { sanitizeUrl } from './sanitize-url';

describe('sanitizeUrl', () => {
  it('should remove hash by default', () => {
    const result = sanitizeUrl('https://example.com/path#section');
    expect(result).not.toContain('#');
  });

  it('should remove auth credentials', () => {
    const result = sanitizeUrl('https://user:pass@example.com/path');
    expect(result).not.toContain('user');
    expect(result).not.toContain('pass');
  });

  it('should preserve query params by default', () => {
    const result = sanitizeUrl('https://example.com/path?foo=bar');
    expect(result).toContain('foo=bar');
  });

  it('should remove query params when option is set', () => {
    const result = sanitizeUrl('https://example.com/path?foo=bar', {
      removeQueryParams: true,
      preserveQueryParams: [],
    });
    expect(result).not.toContain('foo=bar');
  });

  it('should preserve specified query params', () => {
    const result = sanitizeUrl('https://example.com/path?page=1&secret=abc', {
      removeQueryParams: true,
      preserveQueryParams: ['page'],
    });
    expect(result).toContain('page=1');
    expect(result).not.toContain('secret');
  });

  it('should handle malformed URLs gracefully', () => {
    const result = sanitizeUrl('not-a-valid-url?secret=123#hash');
    expect(typeof result).toBe('string');
  });
});
