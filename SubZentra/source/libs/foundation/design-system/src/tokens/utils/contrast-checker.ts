/**
 * WCAG 2.1 Contrast Ratio Utilities
 * Provides accessibility validation for color combinations
 * @module tokens/utils/contrast-checker
 */

import type { HSLColor, RGBColor } from '../types';
import { hslToRgb } from './color-utils';

/**
 * WCAG compliance level
 */
export type WCAGLevel = 'AA' | 'AAA';

/**
 * Result of contrast validation
 */
export interface ContrastResult {
  /** Whether the contrast passes the specified level */
  passes: boolean;
  /** Calculated contrast ratio */
  ratio: number;
  /** Required ratio for the specified level */
  required: number;
  /** WCAG level tested */
  level: WCAGLevel;
  /** Whether large text rules were applied */
  isLargeText: boolean;
}

/**
 * Options for contrast validation
 */
export interface ContrastOptions {
  /** WCAG level to test against (default: 'AA') */
  level?: WCAGLevel;
  /** Whether to use large text thresholds (default: false) */
  isLargeText?: boolean;
}

/**
 * WCAG 2.1 contrast ratio requirements
 *
 * AA Level:
 * - Normal text: 4.5:1
 * - Large text (>= 18pt or >= 14pt bold): 3:1
 *
 * AAA Level:
 * - Normal text: 7:1
 * - Large text: 4.5:1
 */
const CONTRAST_REQUIREMENTS: Record<WCAGLevel, { normal: number; large: number }> = {
  AA: { normal: 4.5, large: 3 },
  AAA: { normal: 7, large: 4.5 },
};

/**
 * Calculates the relative luminance of an RGB color
 * Per WCAG 2.1 definition: https://www.w3.org/WAI/GL/wiki/Relative_luminance
 *
 * @param rgb - RGB color object
 * @returns Relative luminance value (0-1)
 */
export function getRelativeLuminance(rgb: RGBColor): number {
  const [r, g, b] = [rgb.r, rgb.g, rgb.b].map((channel) => {
    const sRGB = channel / 255;
    return sRGB <= 0.03928 ? sRGB / 12.92 : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  });

  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculates the relative luminance from HSL color
 *
 * @param hsl - HSL color object
 * @returns Relative luminance value (0-1)
 */
export function getRelativeLuminanceFromHSL(hsl: HSLColor): number {
  return getRelativeLuminance(hslToRgb(hsl));
}

/**
 * Calculates the contrast ratio between two colors
 * Per WCAG 2.1: https://www.w3.org/WAI/GL/wiki/Contrast_ratio
 *
 * @param color1 - First HSL color
 * @param color2 - Second HSL color
 * @returns Contrast ratio (1:1 to 21:1)
 *
 * @example
 * const ratio = calculateContrastRatio(
 *   { h: 228, s: 6, l: 94 },  // Light text
 *   { h: 228, s: 6, l: 12 }   // Dark background
 * );
 * // ratio ≈ 12.5
 */
export function calculateContrastRatio(color1: HSLColor, color2: HSLColor): number {
  const lum1 = getRelativeLuminanceFromHSL(color1);
  const lum2 = getRelativeLuminanceFromHSL(color2);

  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);

  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Validates if a foreground/background color combination meets WCAG requirements
 *
 * @param foreground - Foreground (text) HSL color
 * @param background - Background HSL color
 * @param options - Validation options
 * @returns ContrastResult with pass/fail and details
 *
 * @example
 * // Validate AA compliance for normal text
 * const result = validateContrast(
 *   { h: 228, s: 6, l: 94 },
 *   { h: 228, s: 6, l: 12 },
 *   { level: 'AA' }
 * );
 *
 * if (result.passes) {
 *   console.log(`Ratio ${result.ratio.toFixed(2)}:1 passes AA`);
 * }
 */
export function validateContrast(
  foreground: HSLColor,
  background: HSLColor,
  options?: ContrastOptions,
): ContrastResult {
  const { level = 'AA', isLargeText = false } = options ?? {};

  const ratio = calculateContrastRatio(foreground, background);
  const requirements = CONTRAST_REQUIREMENTS[level];
  const required = isLargeText ? requirements.large : requirements.normal;

  return {
    passes: ratio >= required,
    ratio: Math.round(ratio * 100) / 100, // Round to 2 decimal places
    required,
    level,
    isLargeText,
  };
}

/**
 * Finds the minimum lightness adjustment needed to meet contrast requirements
 *
 * @param foreground - Foreground HSL color
 * @param background - Background HSL color
 * @param options - Validation options
 * @returns Suggested lightness adjustment or 0 if already passing
 */
export function suggestLightnessAdjustment(
  foreground: HSLColor,
  background: HSLColor,
  options?: ContrastOptions,
): number {
  const result = validateContrast(foreground, background, options);

  if (result.passes) {
    return 0;
  }

  // Binary search for minimum adjustment
  const bgLum = getRelativeLuminanceFromHSL(background);
  const fgLum = getRelativeLuminanceFromHSL(foreground);

  // Determine direction: should foreground be lighter or darker?
  const shouldBeLighter = fgLum > bgLum;

  let low = 0;
  let high = shouldBeLighter ? 100 - foreground.l : foreground.l;
  let adjustment = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const testL = shouldBeLighter ? foreground.l + mid : foreground.l - mid;

    const testResult = validateContrast({ ...foreground, l: testL }, background, options);

    if (testResult.passes) {
      adjustment = shouldBeLighter ? mid : -mid;
      high = mid - 1;
    } else {
      low = mid + 1;
    }
  }

  return adjustment;
}

/**
 * Batch validates multiple foreground colors against a background
 *
 * @param foregrounds - Array of foreground HSL colors with identifiers
 * @param background - Background HSL color
 * @param options - Validation options
 * @returns Map of identifiers to ContrastResults
 */
export function batchValidateContrast(
  foregrounds: Array<{ id: string; color: HSLColor }>,
  background: HSLColor,
  options?: ContrastOptions,
): Map<string, ContrastResult> {
  const results = new Map<string, ContrastResult>();

  for (const { id, color } of foregrounds) {
    results.set(id, validateContrast(color, background, options));
  }

  return results;
}

/**
 * Checks if a color is considered "light" based on luminance
 * Useful for determining appropriate text color
 *
 * @param hsl - HSL color to check
 * @param threshold - Luminance threshold (default: 0.5)
 * @returns true if color is light
 */
export function isLightColor(hsl: HSLColor, threshold = 0.5): boolean {
  return getRelativeLuminanceFromHSL(hsl) > threshold;
}

/**
 * Determines the best text color (black or white) for a given background
 *
 * @param background - Background HSL color
 * @returns 'light' for white text, 'dark' for black text
 */
export function getOptimalTextColor(background: HSLColor): 'light' | 'dark' {
  return isLightColor(background) ? 'dark' : 'light';
}
