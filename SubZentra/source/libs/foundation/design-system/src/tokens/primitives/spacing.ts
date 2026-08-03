/**
 * Spacing Primitives - Tier 1 Tokens
 * Phi-based (√2) spacing scale for visual harmony
 *
 * Design rationale:
 * - Uses √2 (≈1.414) as the ratio for mathematically harmonious spacing
 * - Provides both standard increments and phi-based scale
 * - Supports dynamic spacing that scales with typography
 *
 * @module tokens/primitives/spacing
 */

import type { DimensionToken } from '../types';

/**
 * Mathematical constants for spacing calculations
 * Using √2 (square root of 2) as the golden ratio approximation
 * This creates a visually harmonious progression
 */
export const PHI = 1.41421356237;
export const PHI_INVERSE = 1 / PHI; // ≈ 0.707

/**
 * Powers of phi for scale calculation
 */
export const PHI_POWERS = {
  i6: Math.pow(PHI, -6), // ≈ 0.125
  i5: Math.pow(PHI, -5), // ≈ 0.177
  i4: Math.pow(PHI, -4), // ≈ 0.25
  i3: Math.pow(PHI, -3), // ≈ 0.354
  i2: Math.pow(PHI, -2), // ≈ 0.5
  i1: PHI_INVERSE, // ≈ 0.707
  0: 1, // 1 (base)
  1: PHI, // ≈ 1.414
  2: Math.pow(PHI, 2), // ≈ 2
  3: Math.pow(PHI, 3), // ≈ 2.828
  4: Math.pow(PHI, 4), // ≈ 4
  5: Math.pow(PHI, 5), // ≈ 5.657
  6: Math.pow(PHI, 6), // ≈ 8
} as const;

/**
 * Helper to create spacing token
 */
function createSpacingToken(
  value: string,
  numericValue: number,
  description?: string,
): DimensionToken {
  return {
    $type: 'dimension',
    $value: value,
    $numericValue: numericValue,
    $unit: 'rem',
    ...(description && { $description: description }),
  };
}

/**
 * Spacing scale using phi ratios
 *
 * Scale progression (base = 1rem = 16px):
 * - 5xs: 0.125rem (2px)   - Hairline gaps
 * - 4xs: 0.177rem (2.8px) - Micro spacing
 * - 3xs: 0.25rem (4px)    - Tight spacing
 * - 2xs: 0.354rem (5.7px) - Small gaps
 * - xs:  0.5rem (8px)     - Compact spacing
 * - sm:  0.707rem (11px)  - Small spacing
 * - base: 1rem (16px)     - Default spacing
 * - lg:  1.414rem (23px)  - Large spacing
 * - xl:  2rem (32px)      - Extra large
 * - 2xl: 2.828rem (45px)  - Section spacing
 * - 3xl: 4rem (64px)      - Major sections
 * - 4xl: 5.657rem (90px)  - Page sections
 * - 5xl: 8rem (128px)     - Hero sections
 */
export const spacingPrimitives = {
  /** Zero spacing */
  '0': createSpacingToken('0', 0, 'No spacing'),

  /** 1px spacing */
  px: createSpacingToken('1px', 0.0625, '1 pixel'),

  /** Phi-based scale (negative powers) */
  '5xs': createSpacingToken('0.125rem', 0.125, 'Extra extra extra extra small (2px)'),
  '4xs': createSpacingToken('0.177rem', 0.177, 'Extra extra extra small (2.8px)'),
  '3xs': createSpacingToken('0.25rem', 0.25, 'Extra extra small (4px)'),
  '2xs': createSpacingToken('0.354rem', 0.354, 'Extra small (5.7px)'),
  xs: createSpacingToken('0.5rem', 0.5, 'Small (8px)'),

  /** Transition spacing */
  sm: createSpacingToken('0.707rem', 0.707, 'Small-medium (11px)'),

  /** Base spacing */
  base: createSpacingToken('1rem', 1, 'Base spacing (16px)'),

  /** Phi-based scale (positive powers) */
  lg: createSpacingToken('1.414rem', 1.414, 'Large (23px)'),
  xl: createSpacingToken('2rem', 2, 'Extra large (32px)'),
  '2xl': createSpacingToken('2.828rem', 2.828, 'Extra extra large (45px)'),
  '3xl': createSpacingToken('4rem', 4, 'Extra extra extra large (64px)'),
  '4xl': createSpacingToken('5.657rem', 5.657, 'Huge (90px)'),
  '5xl': createSpacingToken('8rem', 8, 'Massive (128px)'),
} as const satisfies Record<string, DimensionToken>;

/**
 * Standard spacing scale (4px increments)
 * For cases where a standard grid is preferred
 */
export const standardSpacing = {
  '0': createSpacingToken('0', 0, 'No spacing'),
  '0.5': createSpacingToken('0.125rem', 0.125, '2px'),
  '1': createSpacingToken('0.25rem', 0.25, '4px'),
  '1.5': createSpacingToken('0.375rem', 0.375, '6px'),
  '2': createSpacingToken('0.5rem', 0.5, '8px'),
  '2.5': createSpacingToken('0.625rem', 0.625, '10px'),
  '3': createSpacingToken('0.75rem', 0.75, '12px'),
  '3.5': createSpacingToken('0.875rem', 0.875, '14px'),
  '4': createSpacingToken('1rem', 1, '16px'),
  '5': createSpacingToken('1.25rem', 1.25, '20px'),
  '6': createSpacingToken('1.5rem', 1.5, '24px'),
  '7': createSpacingToken('1.75rem', 1.75, '28px'),
  '8': createSpacingToken('2rem', 2, '32px'),
  '9': createSpacingToken('2.25rem', 2.25, '36px'),
  '10': createSpacingToken('2.5rem', 2.5, '40px'),
  '11': createSpacingToken('2.75rem', 2.75, '44px'),
  '12': createSpacingToken('3rem', 3, '48px'),
  '14': createSpacingToken('3.5rem', 3.5, '56px'),
  '16': createSpacingToken('4rem', 4, '64px'),
  '20': createSpacingToken('5rem', 5, '80px'),
  '24': createSpacingToken('6rem', 6, '96px'),
  '28': createSpacingToken('7rem', 7, '112px'),
  '32': createSpacingToken('8rem', 8, '128px'),
} as const satisfies Record<string, DimensionToken>;

/**
 * Border radius tokens
 * Follows a similar scale pattern for consistency
 */
export const radiusPrimitives = {
  none: createSpacingToken('0', 0, 'No radius'),
  sm: createSpacingToken('0.125rem', 0.125, 'Small radius (2px)'),
  default: createSpacingToken('0.25rem', 0.25, 'Default radius (4px)'),
  md: createSpacingToken('0.375rem', 0.375, 'Medium radius (6px)'),
  lg: createSpacingToken('0.5rem', 0.5, 'Large radius (8px)'),
  xl: createSpacingToken('0.75rem', 0.75, 'Extra large radius (12px)'),
  '2xl': createSpacingToken('1rem', 1, 'Extra extra large radius (16px)'),
  '3xl': createSpacingToken('1.5rem', 1.5, 'Very large radius (24px)'),
  full: {
    $type: 'dimension',
    $value: '9999px',
    $numericValue: 9999,
    $unit: 'px',
    $description: 'Fully rounded (pill shape)',
  } as DimensionToken,
} as const;

/**
 * Type for phi-based spacing keys
 */
export type SpacingKey = keyof typeof spacingPrimitives;

/**
 * Type for standard spacing keys
 */
export type StandardSpacingKey = keyof typeof standardSpacing;

/**
 * Type for radius keys
 */
export type RadiusKey = keyof typeof radiusPrimitives;

/**
 * Helper to get CSS variable for spacing
 */
export function spacingVar(key: SpacingKey): string {
  return `var(--spacing-${key})`;
}

/**
 * Helper to get CSS variable for radius
 */
export function radiusVar(key: RadiusKey): string {
  return `var(--radius-${key})`;
}

/**
 * Calculates dynamic spacing based on a multiplier
 * Useful for component-specific spacing that scales with the system
 *
 * @param multiplier - Phi power to use
 * @param base - Base value in rem (default: 1)
 * @returns Spacing value in rem
 */
export function calculatePhiSpacing(multiplier: keyof typeof PHI_POWERS, base = 1): number {
  return Number((base * PHI_POWERS[multiplier]).toFixed(4));
}
