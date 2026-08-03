import { describe, expect, it } from 'vitest';

import { shouldIgnoreUrl } from './should-ignore-url';

describe('shouldIgnoreUrl', () => {
  it('should return false for empty patterns array', () => {
    const result = shouldIgnoreUrl('https://example.com/api/data', []);
    expect(result).toBe(false);
  });

  it('should match URL with regex pattern', () => {
    const result = shouldIgnoreUrl('https://example.com/health', [
      '^https://example\\.com/health$',
    ]);
    expect(result).toBe(true);
  });

  it('should match URL with partial regex pattern', () => {
    const result = shouldIgnoreUrl('https://example.com/api/internal/status', ['internal']);
    expect(result).toBe(true);
  });

  it('should not match non-matching URL', () => {
    const result = shouldIgnoreUrl('https://example.com/api/data', ['/admin', '/internal']);
    expect(result).toBe(false);
  });

  it('should match with plain string pattern when regex is invalid', () => {
    const result = shouldIgnoreUrl('https://example.com/path[bracket', ['[bracket']);
    expect(result).toBe(true);
  });

  it('should return true if any pattern matches', () => {
    const result = shouldIgnoreUrl('https://example.com/health', [
      '/admin',
      '/health',
      '/internal',
    ]);
    expect(result).toBe(true);
  });

  it('should handle multiple patterns', () => {
    const patterns = ['\\.js$', '\\.css$', '\\.png$'];
    expect(shouldIgnoreUrl('https://example.com/app.js', patterns)).toBe(true);
    expect(shouldIgnoreUrl('https://example.com/style.css', patterns)).toBe(true);
    expect(shouldIgnoreUrl('https://example.com/api/data', patterns)).toBe(false);
  });
});
