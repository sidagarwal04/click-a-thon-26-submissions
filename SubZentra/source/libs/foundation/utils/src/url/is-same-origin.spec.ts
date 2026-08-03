import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { isSameOrigin } from './is-same-origin';

describe('isSameOrigin', () => {
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

  it('should return true for same origin URL', () => {
    const result = isSameOrigin('https://example.com/api/data');
    expect(result).toBe(true);
  });

  it('should return true for relative URL', () => {
    const result = isSameOrigin('/api/data');
    expect(result).toBe(true);
  });

  it('should return false for different origin', () => {
    const result = isSameOrigin('https://other-domain.com/api');
    expect(result).toBe(false);
  });

  it('should return false for different protocol', () => {
    const result = isSameOrigin('http://example.com/api');
    expect(result).toBe(false);
  });

  it('should return false for different port', () => {
    const result = isSameOrigin('https://example.com:8080/api');
    expect(result).toBe(false);
  });

  it('should return false for invalid URL', () => {
    const result = isSameOrigin('not-a-valid-url');
    expect(result).toBe(true); // Relative URL treated as same origin
  });

  it('should return false when not in browser', () => {
    // @ts-expect-error - testing undefined case
    delete global.window;
    const result = isSameOrigin('https://example.com/api');
    expect(result).toBe(false);
  });
});
