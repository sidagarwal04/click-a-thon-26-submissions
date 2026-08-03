import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { getCurrentRoute } from './get-current-route';

describe('getCurrentRoute', () => {
  const originalWindow = global.window;

  beforeEach(() => {
    // Mock window.location
    global.window = {
      location: {
        pathname: '/users/profile',
      },
    } as Window & typeof globalThis;
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  it('should return current pathname', () => {
    const result = getCurrentRoute();
    expect(result).toBe('/users/profile');
  });

  it('should return root path', () => {
    global.window = {
      location: {
        pathname: '/',
      },
    } as Window & typeof globalThis;
    const result = getCurrentRoute();
    expect(result).toBe('/');
  });

  it('should return empty string when not in browser', () => {
    // @ts-expect-error - testing undefined case
    delete global.window;
    const result = getCurrentRoute();
    expect(result).toBe('');
  });
});
