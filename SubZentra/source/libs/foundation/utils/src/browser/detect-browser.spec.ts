import { describe, expect, it } from 'vitest';

import { detectBrowser } from './detect-browser';

describe('detectBrowser', () => {
  it('should return browser info object with all required properties', () => {
    const info = detectBrowser();

    expect(info).toHaveProperty('name');
    expect(info).toHaveProperty('version');
    expect(info).toHaveProperty('os');
    expect(info).toHaveProperty('osVersion');
    expect(info).toHaveProperty('deviceType');
    expect(info).toHaveProperty('screenWidth');
    expect(info).toHaveProperty('screenHeight');
    expect(info).toHaveProperty('viewportWidth');
    expect(info).toHaveProperty('viewportHeight');
    expect(info).toHaveProperty('devicePixelRatio');
    expect(info).toHaveProperty('userAgent');
    expect(info).toHaveProperty('language');
    expect(info).toHaveProperty('platform');
    expect(info).toHaveProperty('hardwareConcurrency');
    expect(info).toHaveProperty('touchSupport');
  });

  it('should return valid device type', () => {
    const info = detectBrowser();
    expect(['desktop', 'mobile', 'tablet', 'unknown']).toContain(info.deviceType);
  });

  it('should return numeric values for screen dimensions', () => {
    const info = detectBrowser();
    expect(typeof info.screenWidth).toBe('number');
    expect(typeof info.screenHeight).toBe('number');
    expect(typeof info.viewportWidth).toBe('number');
    expect(typeof info.viewportHeight).toBe('number');
    expect(typeof info.devicePixelRatio).toBe('number');
  });

  it('should return unknown values when not in browser', () => {
    const originalWindow = global.window;
    // @ts-expect-error - testing undefined case
    delete global.window;

    const info = detectBrowser();
    expect(info.name).toBe('unknown');
    expect(info.deviceType).toBe('unknown');

    global.window = originalWindow;
  });
});
