/**
 * Color Primitives - Tier 1 Tokens
 * Raw HSL-based color values following Linear's design language
 *
 * Color Philosophy:
 * - Low saturation neutrals for minimal, clean aesthetic
 * - Desaturated accent for professional feel
 * - Full scale (80-1000) for fine-grained control
 *
 * @module tokens/primitives/colors
 */

import type { ColorToken } from '../types';
import { createColorToken, generateColorScale } from '../utils/color-utils';

/**
 * Color definition with HSL base values
 * These are the foundation for generated color scales
 */
export interface ColorDefinition {
  /** Hue value (0-360) */
  readonly h: number;
  /** Saturation value (0-100) */
  readonly s: number;
  /** Description for documentation */
  readonly description?: string;
}

/**
 * Linear-style color definitions
 *
 * Design rationale:
 * - Accent: Desaturated indigo-blue (#5E6AD2) - professional, not overwhelming
 * - Neutral: Cool gray with subtle blue undertone - modern, not sterile
 * - Alert/Destructive: High saturation red for clear danger signals
 * - Success: Medium saturation green - visible but not jarring
 * - Warning: Warm amber - attention-getting without alarm
 * - Smart: Vivid violet - distinct for AI/intelligent features
 * - Info: Bright blue - informational, trustworthy
 */
export const COLOR_DEFINITIONS = {
  /** Primary accent - desaturated indigo-blue like Linear */
  accent: { h: 235, s: 56, description: 'Primary accent color' },

  /** Neutral gray - subtle cool undertone */
  neutral: { h: 228, s: 6, description: 'Neutral gray scale' },

  /** Alert/Error - high visibility red */
  alert: { h: 0, s: 72, description: 'Error and destructive actions' },

  /** Warning - attention-getting amber */
  warning: { h: 45, s: 74, description: 'Warning and caution states' },

  /** Success - positive feedback green */
  success: { h: 142, s: 55, description: 'Success and positive states' },

  /** Smart/AI - distinctive violet */
  smart: { h: 256, s: 94, description: 'AI and intelligent features' },

  /** Info - informational blue */
  info: { h: 210, s: 80, description: 'Informational states' },
} as const satisfies Record<string, ColorDefinition>;

/**
 * Type for color scale names
 */
export type ColorScaleName = keyof typeof COLOR_DEFINITIONS;

/**
 * Generated color scales (80-1000 steps)
 * Each scale provides fine-grained lightness control
 *
 * Usage:
 * - 80-200: Lightest shades (backgrounds, subtle fills)
 * - 200-400: Light shades (hover states, borders)
 * - 400-600: Mid tones (secondary text, icons)
 * - 600-800: Dark shades (primary text in light mode)
 * - 800-1000: Darkest shades (text in dark mode backgrounds)
 */
export const accentScale = generateColorScale(
  'accent',
  COLOR_DEFINITIONS.accent.h,
  COLOR_DEFINITIONS.accent.s,
);

export const neutralScale = generateColorScale(
  'neutral',
  COLOR_DEFINITIONS.neutral.h,
  COLOR_DEFINITIONS.neutral.s,
);

export const alertScale = generateColorScale(
  'alert',
  COLOR_DEFINITIONS.alert.h,
  COLOR_DEFINITIONS.alert.s,
);

export const warningScale = generateColorScale(
  'warning',
  COLOR_DEFINITIONS.warning.h,
  COLOR_DEFINITIONS.warning.s,
);

export const successScale = generateColorScale(
  'success',
  COLOR_DEFINITIONS.success.h,
  COLOR_DEFINITIONS.success.s,
);

export const smartScale = generateColorScale(
  'smart',
  COLOR_DEFINITIONS.smart.h,
  COLOR_DEFINITIONS.smart.s,
);

export const infoScale = generateColorScale(
  'info',
  COLOR_DEFINITIONS.info.h,
  COLOR_DEFINITIONS.info.s,
);

/**
 * Static colors - non-scale colors for specific use cases
 */
export const staticColors = {
  /** Pure white */
  white: createColorToken(0, 0, 100, 'Pure white'),

  /** Pure black */
  black: createColorToken(0, 0, 0, 'Pure black'),

  /** Linear Mercury White - primary light text/highlight */
  mercuryWhite: createColorToken(228, 15, 96, 'Linear Mercury White (#F4F5F8)'),

  /** Linear Nordic Gray - primary dark background */
  nordicGray: createColorToken(228, 4, 14, 'Linear Nordic Gray (#222326)'),

  /** Transparent */
  transparent: {
    $type: 'color',
    $value: 'transparent',
    $hsl: { h: 0, s: 0, l: 0, a: 0 },
    $description: 'Transparent color',
  } as ColorToken,

  /** Current color (inherit) */
  current: {
    $type: 'color',
    $value: 'currentColor',
    $hsl: { h: 0, s: 0, l: 0 },
    $description: 'Current/inherited color',
  } as ColorToken,
} as const;

/**
 * Combined color primitives export
 * All color scales and static colors in one object
 */
export const colorPrimitives = {
  accent: accentScale,
  neutral: neutralScale,
  alert: alertScale,
  warning: warningScale,
  success: successScale,
  smart: smartScale,
  info: infoScale,
  static: staticColors,
} as const;

/**
 * Type-safe accessor for neutral scale tokens
 */
export type NeutralStep = keyof typeof neutralScale;

/**
 * Type-safe accessor for accent scale tokens
 */
export type AccentStep = keyof typeof accentScale;

/**
 * Helper function to get a specific color from a scale
 *
 * @param scale - Color scale name
 * @param step - Step number (80-1000)
 * @returns ColorToken or undefined
 *
 * @example
 * const color = getScaleColor('neutral', 200);
 * // color.$value = 'hsl(228 6% 80%)'
 */
export function getScaleColor(scale: ColorScaleName, step: number): ColorToken | undefined {
  const scaleObj = colorPrimitives[scale];
  if (typeof scaleObj === 'object' && scaleObj !== null) {
    const key = `${scale}-${step}`;
    return (scaleObj as Record<string, ColorToken>)[key];
  }
  return undefined;
}

/**
 * Helper to create a color CSS variable reference
 *
 * @param scale - Color scale name
 * @param step - Step number
 * @returns CSS var() reference string
 *
 * @example
 * const ref = colorVar('neutral', 200);
 * // 'var(--color-neutral-200)'
 */
export function colorVar(scale: ColorScaleName, step: number): string {
  return `var(--color-${scale}-${step})`;
}
