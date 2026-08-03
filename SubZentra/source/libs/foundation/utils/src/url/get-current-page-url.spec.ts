import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { getCurrentPageUrl } from './get-current-page-url';

describe('getCurrentPageUrl', () => {
  const originalWindow = global.window;

  beforeEach(() => {
    // Mock window.location
    global.window = {
      location: {
        origin: 'https://example.com',
        href: 'https://example.com/page?query=value#section',
      },
    } as Window & typeof globalThis;
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  it('should return sanitized current URL', () => {
    const result = getCurrentPageUrl();
    expect(result).toContain('https://example.com/page');
  });

  it('should remove hash by default', () => {
    const result = getCurrentPageUrl();
    expect(result).not.toContain('#section');
  });

  it('should preserve query params by default', () => {
    const result = getCurrentPageUrl();
    expect(result).toContain('query=value');
  });

  it('should remove query params when option is set', () => {
    const result = getCurrentPageUrl({ removeQueryParams: true, preserveQueryParams: [] });
    expect(result).not.toContain('query=value');
  });

  it('should return empty string when not in browser', () => {
    // @ts-expect-error - testing undefined case
    delete global.window;
    const result = getCurrentPageUrl();
    expect(result).toBe('');
  });
});
