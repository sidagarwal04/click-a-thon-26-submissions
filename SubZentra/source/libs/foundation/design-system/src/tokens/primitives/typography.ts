/**
 * Typography Primitives - Tier 1 Tokens
 * Font metrics, weights, and text style presets
 *
 * Design rationale:
 * - Variable font weights for Inter variable font support
 * - Negative letter-spacing for tighter, modern look (Linear-style)
 * - Responsive font sizes with device-specific adjustments
 *
 * @module tokens/primitives/typography
 */

import type { DimensionToken, FontFamilyToken, FontWeightToken, NumberToken } from '../types';

/**
 * Font weight tokens for variable fonts
 * Values optimized for Inter variable font
 *
 * Standard weights mapped to variable font values:
 * - thin: 80 (extra light)
 * - light: 210
 * - regular: 440 (slightly heavier than 400 for better readability)
 * - medium: 530
 * - semibold: 600
 * - bold: 700
 * - heavy: 840 (extra bold)
 */
export const fontWeights = {
  thin: {
    $type: 'fontWeight',
    $value: 80,
    $name: 'thin',
    $description: 'Extra light weight for decorative use',
  },
  light: {
    $type: 'fontWeight',
    $value: 210,
    $name: 'light',
    $description: 'Light weight for secondary text',
  },
  regular: {
    $type: 'fontWeight',
    $value: 440,
    $name: 'regular',
    $description: 'Default body text weight',
  },
  medium: {
    $type: 'fontWeight',
    $value: 530,
    $name: 'medium',
    $description: 'Medium emphasis text',
  },
  semibold: {
    $type: 'fontWeight',
    $value: 600,
    $name: 'semibold',
    $description: 'Strong emphasis, UI labels',
  },
  bold: {
    $type: 'fontWeight',
    $value: 700,
    $name: 'bold',
    $description: 'Headings and strong emphasis',
  },
  heavy: {
    $type: 'fontWeight',
    $value: 840,
    $name: 'heavy',
    $description: 'Extra bold for impact',
  },
} as const satisfies Record<string, FontWeightToken>;

/**
 * Font family stacks
 * Primary: Inter variable with system fallbacks
 * Mono: JetBrains Mono for code
 */
export const fontFamilies = {
  sans: {
    $type: 'fontFamily',
    $value:
      '"Inter var", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    $fallbacks: [
      'Inter',
      '-apple-system',
      'BlinkMacSystemFont',
      'Segoe UI',
      'system-ui',
      'sans-serif',
    ],
    $description: 'Primary sans-serif font stack',
  },
  mono: {
    $type: 'fontFamily',
    $value: '"JetBrains Mono", "SF Mono", "Fira Code", Consolas, "Liberation Mono", monospace',
    $fallbacks: ['SF Mono', 'Fira Code', 'Consolas', 'Liberation Mono', 'monospace'],
    $description: 'Monospace font for code',
  },
} as const satisfies Record<string, FontFamilyToken>;

/**
 * Helper to create dimension token for typography
 */
function createDimensionToken(
  value: string,
  numericValue: number,
  unit: 'px' | 'rem' | 'em',
  description?: string,
): DimensionToken {
  return {
    $type: 'dimension',
    $value: value,
    $numericValue: numericValue,
    $unit: unit,
    ...(description && { $description: description }),
  };
}

/**
 * Helper to create number token for line-height
 */
function createNumberToken(value: number, description?: string): NumberToken {
  return {
    $type: 'number',
    $value: value,
    ...(description && { $description: description }),
  };
}

/**
 * Text style interface for composite typography tokens
 */
export interface TextStyleDefinition {
  readonly fontSize: DimensionToken;
  readonly lineHeight: NumberToken;
  readonly letterSpacing: DimensionToken;
  readonly fontWeight?: FontWeightToken;
}

/**
 * Text style presets
 *
 * Naming convention follows semantic hierarchy:
 * - title-*: Page/section headings
 * - subtitle-*: Subheadings
 * - body/body-*: Main content text
 * - system/system-*: UI text (buttons, labels)
 * - caption: Small helper text
 * - footnote: Smallest text for legal/fine print
 *
 * All styles include:
 * - fontSize: The size of the text
 * - lineHeight: Unitless multiplier for line-height
 * - letterSpacing: Tracking (negative for tighter text)
 */
export const textStyles = {
  'title-large': {
    fontSize: createDimensionToken('1.625rem', 26, 'px', 'Large title size'),
    lineHeight: createNumberToken(1.2, 'Tight line height for titles'),
    letterSpacing: createDimensionToken('-0.02em', -0.02, 'em', 'Tight tracking'),
  },
  'title-1': {
    fontSize: createDimensionToken('1.375rem', 22, 'px', 'Title 1 size'),
    lineHeight: createNumberToken(1.35, 'Title line height'),
    letterSpacing: createDimensionToken('-0.015em', -0.015, 'em', 'Slight negative tracking'),
  },
  'title-2': {
    fontSize: createDimensionToken('1.125rem', 18, 'px', 'Title 2 size'),
    lineHeight: createNumberToken(1.35, 'Title line height'),
    letterSpacing: createDimensionToken('-0.015em', -0.015, 'em', 'Slight negative tracking'),
  },
  'title-3': {
    fontSize: createDimensionToken('1rem', 16, 'px', 'Title 3 size'),
    lineHeight: createNumberToken(1.35, 'Title line height'),
    letterSpacing: createDimensionToken('-0.015em', -0.015, 'em', 'Slight negative tracking'),
  },
  'subtitle-1': {
    fontSize: createDimensionToken('1rem', 16, 'px', 'Subtitle 1 size'),
    lineHeight: createNumberToken(1.4, 'Subtitle line height'),
    letterSpacing: createDimensionToken('-0.015em', -0.015, 'em', 'Slight negative tracking'),
  },
  'subtitle-2': {
    fontSize: createDimensionToken('0.9375rem', 15, 'px', 'Subtitle 2 size'),
    lineHeight: createNumberToken(1.35, 'Subtitle line height'),
    letterSpacing: createDimensionToken('-0.02em', -0.02, 'em', 'Tighter tracking'),
  },
  body: {
    fontSize: createDimensionToken('0.9375rem', 15, 'px', 'Default body size'),
    lineHeight: createNumberToken(1.5, 'Comfortable reading line height'),
    letterSpacing: createDimensionToken('-0.0175em', -0.0175, 'em', 'Slight negative tracking'),
  },
  'body-large': {
    fontSize: createDimensionToken('1rem', 16, 'px', 'Large body size'),
    lineHeight: createNumberToken(1.6, 'Relaxed line height for long-form'),
    letterSpacing: createDimensionToken('-0.015em', -0.015, 'em', 'Slight negative tracking'),
  },
  'body-small': {
    fontSize: createDimensionToken('0.875rem', 14, 'px', 'Small body size'),
    lineHeight: createNumberToken(1.4, 'Compact line height'),
    letterSpacing: createDimensionToken('-0.015em', -0.015, 'em', 'Slight negative tracking'),
  },
  system: {
    fontSize: createDimensionToken('0.8125rem', 13, 'px', 'Default UI text size'),
    lineHeight: createNumberToken(1.32, 'Compact UI line height'),
    letterSpacing: createDimensionToken('-0.005em', -0.005, 'em', 'Minimal tracking adjustment'),
  },
  'system-small': {
    fontSize: createDimensionToken('0.75rem', 12, 'px', 'Small UI text size'),
    lineHeight: createNumberToken(1.35, 'Compact line height'),
    letterSpacing: createDimensionToken('-0.01em', -0.01, 'em', 'Slight negative tracking'),
  },
  caption: {
    fontSize: createDimensionToken('0.75rem', 12, 'px', 'Caption size'),
    lineHeight: createNumberToken(1.35, 'Caption line height'),
    letterSpacing: createDimensionToken('0em', 0, 'em', 'No tracking adjustment'),
  },
  footnote: {
    fontSize: createDimensionToken('0.6875rem', 11, 'px', 'Footnote size'),
    lineHeight: createNumberToken(1.4, 'Footnote line height'),
    letterSpacing: createDimensionToken('-0.005em', -0.005, 'em', 'Minimal tracking'),
  },
} as const satisfies Record<string, TextStyleDefinition>;

/**
 * Type for text style names
 */
export type TextStyleKey = keyof typeof textStyles;

/**
 * Type for font weight names
 */
export type FontWeightKey = keyof typeof fontWeights;

/**
 * Type for font family names
 */
export type FontFamilyKey = keyof typeof fontFamilies;

/**
 * Combined typography primitives export
 */
export const typographyPrimitives = {
  fontWeights,
  fontFamilies,
  textStyles,
} as const;

/**
 * Helper to get CSS variable for font weight
 */
export function fontWeightVar(weight: FontWeightKey): string {
  return `var(--font-weight-${weight})`;
}

/**
 * Helper to get CSS variable for font family
 */
export function fontFamilyVar(family: FontFamilyKey): string {
  return `var(--font-family-${family})`;
}
