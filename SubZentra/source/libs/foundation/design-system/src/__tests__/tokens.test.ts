/**
 * Token System Tests
 * Validates token integrity, contrast ratios, and theme compliance
 *
 * @module __tests__/tokens
 */

import { describe, expect, it } from 'vitest';

import { darkTheme } from '../tokens/themes/dark';
import { lightTheme } from '../tokens/themes/light';
import type { ThemeContract } from '../tokens/themes/theme-contract';
import type { HSLColor } from '../tokens/types';
import {
  createColorToken,
  DEFAULT_COLOR_STEPS,
  generateColorScale,
  hexToHsl,
  hslToHex,
} from '../tokens/utils/color-utils';
import {
  calculateContrastRatio,
  getOptimalTextColor,
  isLightColor,
  validateContrast,
} from '../tokens/utils/contrast-checker';

// =============================================================================
// COLOR UTILITIES TESTS
// =============================================================================

describe('Color Utilities', () => {
  describe('createColorToken', () => {
    it('creates a valid color token', () => {
      const token = createColorToken(235, 56, 60);

      expect(token.$type).toBe('color');
      expect(token.$value).toBe('hsl(235 56% 60%)');
      expect(token.$hsl).toEqual({ h: 235, s: 56, l: 60 });
    });

    it('includes description when provided', () => {
      const token = createColorToken(235, 56, 60, 'Test color');

      expect(token.$description).toBe('Test color');
    });
  });

  describe('generateColorScale', () => {
    it('generates a color scale with correct steps', () => {
      const scale = generateColorScale('test', 228, 6);

      // The ramp is deliberately non-uniform — denser at the ends, sparser
      // through the middle (…480, 560, 620…) — so there is no 500, which is
      // what this assertion used to look for. Comparing against the exported
      // step list is both stronger and immune to that mistake recurring.
      expect(Object.keys(scale)).toEqual(DEFAULT_COLOR_STEPS.map((step) => `test-${step}`));
    });

    it('generates colors with correct HSL values', () => {
      const scale = generateColorScale('neutral', 228, 6);

      // Check that scale-80 is the lightest
      expect(scale['neutral-80'].$hsl.l).toBeGreaterThan(scale['neutral-1000'].$hsl.l);
    });
  });

  describe('hslToHex', () => {
    it('converts HSL to hex correctly', () => {
      // Pure white
      expect(hslToHex({ h: 0, s: 0, l: 100 })).toBe('#FFFFFF');

      // Pure black
      expect(hslToHex({ h: 0, s: 0, l: 0 })).toBe('#000000');

      // Pure red
      expect(hslToHex({ h: 0, s: 100, l: 50 })).toBe('#FF0000');
    });
  });

  describe('hexToHsl', () => {
    it('converts hex to HSL correctly', () => {
      const white = hexToHsl('#FFFFFF');
      expect(white?.l).toBe(100);

      const black = hexToHsl('#000000');
      expect(black?.l).toBe(0);
    });

    it('returns null for invalid hex', () => {
      expect(hexToHsl('invalid')).toBeNull();
      expect(hexToHsl('#GGG')).toBeNull();
    });
  });
});

// =============================================================================
// CONTRAST CHECKER TESTS
// =============================================================================

describe('Contrast Checker', () => {
  describe('calculateContrastRatio', () => {
    it('calculates correct contrast between black and white', () => {
      const white: HSLColor = { h: 0, s: 0, l: 100 };
      const black: HSLColor = { h: 0, s: 0, l: 0 };

      const ratio = calculateContrastRatio(white, black);

      // Black and white should have 21:1 contrast
      expect(ratio).toBeCloseTo(21, 0);
    });

    it('calculates symmetric contrast', () => {
      const color1: HSLColor = { h: 228, s: 6, l: 94 };
      const color2: HSLColor = { h: 228, s: 6, l: 12 };

      const ratio1 = calculateContrastRatio(color1, color2);
      const ratio2 = calculateContrastRatio(color2, color1);

      expect(ratio1).toBeCloseTo(ratio2, 2);
    });
  });

  describe('validateContrast', () => {
    it('validates WCAG AA for normal text (4.5:1)', () => {
      // High contrast combo should pass
      const result = validateContrast(
        { h: 228, s: 6, l: 94 }, // Light text
        { h: 228, s: 6, l: 12 }, // Dark background
        { level: 'AA' },
      );

      expect(result.passes).toBe(true);
      expect(result.ratio).toBeGreaterThanOrEqual(4.5);
    });

    it('validates WCAG AA for large text (3:1)', () => {
      const result = validateContrast(
        { h: 228, s: 6, l: 74 }, // Secondary text
        { h: 228, s: 6, l: 12 }, // Dark background
        { level: 'AA', isLargeText: true },
      );

      expect(result.required).toBe(3);
    });

    it('validates WCAG AAA for normal text (7:1)', () => {
      const result = validateContrast(
        { h: 0, s: 0, l: 100 },
        { h: 0, s: 0, l: 0 },
        { level: 'AAA' },
      );

      expect(result.passes).toBe(true);
      expect(result.required).toBe(7);
    });
  });

  describe('isLightColor', () => {
    it('correctly identifies light colors', () => {
      expect(isLightColor({ h: 0, s: 0, l: 100 })).toBe(true);
      expect(isLightColor({ h: 0, s: 0, l: 90 })).toBe(true);
    });

    it('correctly identifies dark colors', () => {
      expect(isLightColor({ h: 0, s: 0, l: 0 })).toBe(false);
      expect(isLightColor({ h: 0, s: 0, l: 20 })).toBe(false);
    });
  });

  describe('getOptimalTextColor', () => {
    it('returns dark text for light backgrounds', () => {
      expect(getOptimalTextColor({ h: 0, s: 0, l: 100 })).toBe('dark');
    });

    it('returns light text for dark backgrounds', () => {
      expect(getOptimalTextColor({ h: 0, s: 0, l: 10 })).toBe('light');
    });
  });
});

// =============================================================================
// THEME CONTRACT TESTS
// =============================================================================

describe('Theme Contract Compliance', () => {
  const validateTheme = (theme: ThemeContract) => {
    // Basic structure
    expect(theme.name).toBeDefined();
    expect(theme.mode).toMatch(/^(light|dark)$/);

    // Background tokens
    expect(theme.colors.background.layer00).toBeDefined();
    expect(theme.colors.background.layer01).toBeDefined();
    expect(theme.colors.background.layer02).toBeDefined();
    expect(theme.colors.background.layer03).toBeDefined();
    expect(theme.colors.background.overlay).toBeDefined();

    // Text tokens
    expect(theme.colors.text.highlight).toBeDefined();
    expect(theme.colors.text.primary).toBeDefined();
    expect(theme.colors.text.secondary).toBeDefined();
    expect(theme.colors.text.tertiary).toBeDefined();
    expect(theme.colors.text.muted).toBeDefined();
    expect(theme.colors.text.inverted).toBeDefined();

    // Interactive tokens
    expect(theme.colors.interactive.primary.resting).toBeDefined();
    expect(theme.colors.interactive.primary.hovered).toBeDefined();
    expect(theme.colors.interactive.primary.pressed).toBeDefined();
    expect(theme.colors.interactive.secondary.resting).toBeDefined();
    expect(theme.colors.interactive.tertiary.resting).toBeDefined();
    expect(theme.colors.interactive.destructive.resting).toBeDefined();
    expect(theme.colors.interactive.smart.resting).toBeDefined();

    // Border tokens
    expect(theme.colors.border.default).toBeDefined();
    expect(theme.colors.border.subtle).toBeDefined();
    expect(theme.colors.border.emphasis).toBeDefined();
    expect(theme.colors.border.focus).toBeDefined();

    // Feedback tokens
    expect(theme.colors.feedback.success).toBeDefined();
    expect(theme.colors.feedback.warning).toBeDefined();
    expect(theme.colors.feedback.error).toBeDefined();
    expect(theme.colors.feedback.info).toBeDefined();

    // Effect tokens
    expect(theme.effects.shadow.depth01).toBeDefined();
    expect(theme.effects.shadow.depth02).toBeDefined();
    expect(theme.effects.shadow.depth03).toBeDefined();
    expect(theme.effects.shadow.depth04).toBeDefined();
    expect(theme.effects.focus.ring).toBeDefined();
    expect(theme.effects.focus.ringOffset).toBeDefined();
  };

  it('dark theme implements full contract', () => {
    validateTheme(darkTheme);
    expect(darkTheme.mode).toBe('dark');
  });

  it('light theme implements full contract', () => {
    validateTheme(lightTheme);
    expect(lightTheme.mode).toBe('light');
  });
});

// =============================================================================
// DARK THEME COLOR CONTRAST TESTS
// =============================================================================

describe('Dark Theme Accessibility', () => {
  // Parse HSL from theme string format "hsl(228 6% 94%)"
  const parseHsl = (hslString: string): HSLColor => {
    const match = hslString.match(/hsl\((\d+)\s+(\d+)%\s+(\d+)%\)/);
    if (!match) throw new Error(`Invalid HSL string: ${hslString}`);
    return {
      h: parseInt(match[1], 10),
      s: parseInt(match[2], 10),
      l: parseInt(match[3], 10),
    };
  };

  it('primary text has sufficient contrast on layer01', () => {
    const text = parseHsl(darkTheme.colors.text.primary);
    const bg = parseHsl(darkTheme.colors.background.layer01);

    const result = validateContrast(text, bg, { level: 'AA' });
    expect(result.passes).toBe(true);
    expect(result.ratio).toBeGreaterThanOrEqual(4.5);
  });

  it('secondary text has sufficient contrast for large text', () => {
    const text = parseHsl(darkTheme.colors.text.secondary);
    const bg = parseHsl(darkTheme.colors.background.layer01);

    const result = validateContrast(text, bg, { level: 'AA', isLargeText: true });
    expect(result.passes).toBe(true);
  });

  it('highlight text has highest contrast', () => {
    const highlight = parseHsl(darkTheme.colors.text.highlight);
    const primary = parseHsl(darkTheme.colors.text.primary);
    const bg = parseHsl(darkTheme.colors.background.layer01);

    const highlightRatio = calculateContrastRatio(highlight, bg);
    const primaryRatio = calculateContrastRatio(primary, bg);

    expect(highlightRatio).toBeGreaterThanOrEqual(primaryRatio);
  });
});

// =============================================================================
// LIGHT THEME COLOR CONTRAST TESTS
// =============================================================================

describe('Light Theme Accessibility', () => {
  const parseHsl = (hslString: string): HSLColor => {
    const match = hslString.match(/hsl\((\d+)\s+(\d+)%\s+(\d+)%\)/);
    if (!match) throw new Error(`Invalid HSL string: ${hslString}`);
    return {
      h: parseInt(match[1], 10),
      s: parseInt(match[2], 10),
      l: parseInt(match[3], 10),
    };
  };

  it('primary text has sufficient contrast on layer01', () => {
    const text = parseHsl(lightTheme.colors.text.primary);
    const bg = parseHsl(lightTheme.colors.background.layer01);

    const result = validateContrast(text, bg, { level: 'AA' });
    expect(result.passes).toBe(true);
    expect(result.ratio).toBeGreaterThanOrEqual(4.5);
  });

  it('text hierarchy is inverted from dark theme', () => {
    const darkHighlight = parseHsl(darkTheme.colors.text.highlight);
    const lightHighlight = parseHsl(lightTheme.colors.text.highlight);

    // In dark theme, highlight should be light; in light theme, highlight should be dark
    expect(darkHighlight.l).toBeGreaterThan(50);
    expect(lightHighlight.l).toBeLessThan(50);
  });
});
