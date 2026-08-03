/**
 * W3C Design Tokens Format compliant type definitions
 * @see https://design-tokens.github.io/community-group/format/
 * @module tokens/types
 */

/**
 * Supported token types per W3C Design Tokens specification
 */
export const TOKEN_TYPE = {
  COLOR: 'color',
  DIMENSION: 'dimension',
  FONT_FAMILY: 'fontFamily',
  FONT_WEIGHT: 'fontWeight',
  DURATION: 'duration',
  CUBIC_BEZIER: 'cubicBezier',
  NUMBER: 'number',
  SHADOW: 'shadow',
  STROKE_STYLE: 'strokeStyle',
  BORDER: 'border',
  TRANSITION: 'transition',
  GRADIENT: 'gradient',
} as const;

export type TokenType = (typeof TOKEN_TYPE)[keyof typeof TOKEN_TYPE];

export const WCAG_LEVEL = {
  AA: 'AA',
  AAA: 'AAA',
} as const;

export type WcagLevel = (typeof WCAG_LEVEL)[keyof typeof WCAG_LEVEL];

/**
 * Extension namespace for vendor-specific metadata
 * Following W3C convention of reverse domain notation
 */
export interface TokenExtensions {
  /** Figma variable sync metadata */
  'com.figma'?: {
    variableId: string;
    collectionId?: string;
  };
  /** Accessibility metadata */
  'com.a11y'?: {
    contrastRatio?: number;
    wcagLevel?: WcagLevel;
    contrastPair?: string;
  };
  /** Platform-specific overrides */
  'com.platform'?: {
    ios?: string;
    android?: string;
    web?: string;
  };
  /** Custom extensions */
  [key: `com.${string}`]: unknown;
}

/**
 * Base token structure following W3C Design Tokens spec
 * All tokens must implement this interface
 */
export interface DesignToken<T = unknown> {
  /** The resolved value of the token */
  readonly $value: T;
  /** Token type for validation and transformation */
  readonly $type: TokenType;
  /** Human-readable description for documentation */
  readonly $description?: string;
  /** Deprecation notice - string provides migration path */
  readonly $deprecated?: boolean | string;
  /** Vendor extensions namespace */
  readonly $extensions?: TokenExtensions;
}

/**
 * Token reference syntax for aliasing
 * Format: {group.token} or {token}
 */
export type TokenReference = `{${string}}`;

/**
 * HSL color value structure
 * Used for color manipulation and contrast calculations
 */
export interface HSLColor {
  /** Hue: 0-360 degrees */
  readonly h: number;
  /** Saturation: 0-100 percentage */
  readonly s: number;
  /** Lightness: 0-100 percentage */
  readonly l: number;
  /** Alpha: 0-1 opacity (optional) */
  readonly a?: number;
}

/**
 * RGB color value structure
 * Used for luminance calculations
 */
export interface RGBColor {
  /** Red: 0-255 */
  readonly r: number;
  /** Green: 0-255 */
  readonly g: number;
  /** Blue: 0-255 */
  readonly b: number;
  /** Alpha: 0-1 opacity (optional) */
  readonly a?: number;
}

/**
 * Color token with HSL metadata for manipulation
 */
export interface ColorToken extends DesignToken<string> {
  readonly $type: 'color';
  /** Raw HSL components for calculations */
  readonly $hsl: HSLColor;
}

/**
 * Supported dimension units
 */
export const DIMENSION_UNIT = {
  PX: 'px',
  REM: 'rem',
  EM: 'em',
  PERCENT: '%',
  VW: 'vw',
  VH: 'vh',
  DVH: 'dvh',
  SVH: 'svh',
  LVH: 'lvh',
} as const;

export type DimensionUnit = (typeof DIMENSION_UNIT)[keyof typeof DIMENSION_UNIT];

/**
 * Dimension token for spacing, sizing, and measurements
 */
export interface DimensionToken extends DesignToken<string> {
  readonly $type: 'dimension';
  /** Numeric value for calculations */
  readonly $numericValue: number;
  /** Unit of measurement */
  readonly $unit: DimensionUnit;
}

/**
 * Font weight token supporting variable fonts
 */
export interface FontWeightToken extends DesignToken<number> {
  readonly $type: 'fontWeight';
  /** Human-readable weight name */
  readonly $name?: string;
}

/**
 * Font family token
 */
export interface FontFamilyToken extends DesignToken<string> {
  readonly $type: 'fontFamily';
  /** Fallback stack as array */
  readonly $fallbacks?: readonly string[];
}

/**
 * Duration token for animations
 */
export interface DurationToken extends DesignToken<string> {
  readonly $type: 'duration';
  /** Numeric value in milliseconds */
  readonly $ms: number;
}

/**
 * Cubic bezier easing token
 */
export interface CubicBezierToken extends DesignToken<string> {
  readonly $type: 'cubicBezier';
  /** Bezier control points [x1, y1, x2, y2] */
  readonly $points?: readonly [number, number, number, number];
}

/**
 * Shadow token for box-shadow values
 */
export interface ShadowToken extends DesignToken<string> {
  readonly $type: 'shadow';
  /** Individual shadow layers */
  readonly $layers?: readonly ShadowLayer[];
}

/**
 * Individual shadow layer definition
 */
export interface ShadowLayer {
  readonly offsetX: number;
  readonly offsetY: number;
  readonly blur: number;
  readonly spread: number;
  readonly color: string;
  readonly inset?: boolean;
}

/**
 * Number token for unitless values
 */
export interface NumberToken extends DesignToken<number> {
  readonly $type: 'number';
}

/**
 * Typography composite token
 * Groups related typography properties
 */
export interface TypographyToken {
  readonly fontSize: DimensionToken;
  readonly lineHeight: DimensionToken | NumberToken;
  readonly letterSpacing: DimensionToken;
  readonly fontWeight?: FontWeightToken;
  readonly fontFamily?: FontFamilyToken;
}

/**
 * Token group structure for organizing tokens
 */
export interface TokenGroup<T extends DesignToken = DesignToken> {
  readonly $description?: string;
  readonly $extensions?: TokenExtensions;
  readonly [key: string]: T | TokenGroup<T> | string | TokenExtensions | undefined;
}

/**
 * Type guard to check if value is a DesignToken
 */
export function isDesignToken(value: unknown): value is DesignToken {
  return typeof value === 'object' && value !== null && '$value' in value && '$type' in value;
}

/**
 * Type guard to check if value is a ColorToken
 */
export function isColorToken(value: unknown): value is ColorToken {
  return isDesignToken(value) && value.$type === 'color' && '$hsl' in value;
}

/**
 * Type guard to check if value is a DimensionToken
 */
export function isDimensionToken(value: unknown): value is DimensionToken {
  return isDesignToken(value) && value.$type === 'dimension';
}

/**
 * Type guard to check if string is a token reference
 */
export function isTokenReference(value: string): value is TokenReference {
  return /^\{[^}]+\}$/.test(value);
}
