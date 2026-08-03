import { afterEach, describe, expect, it } from 'vitest';

import { isBrowser } from './is-browser';

describe('isBrowser', () => {
  const originalWindow = global.window;
  const originalDocument = global.document;

  afterEach(() => {
    // Restore original globals
    if (originalWindow !== undefined) {
      global.window = originalWindow;
    }
    if (originalDocument !== undefined) {
      global.document = originalDocument;
    }
  });

  it('should return true when window and document are defined', () => {
    // In jsdom/vitest, window and document are defined
    expect(isBrowser()).toBe(true);
  });

  it('should return false when window is undefined', () => {
    // @ts-expect-error - testing undefined case
    delete global.window;
    expect(isBrowser()).toBe(false);
  });

  it('should return false when document is undefined', () => {
    // @ts-expect-error - testing undefined case
    delete global.document;
    expect(isBrowser()).toBe(false);
  });
});
