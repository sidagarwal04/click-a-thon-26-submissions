/**
 * Token type definitions - Public API
 * @module tokens/types
 */

export type {
  // Core types
  TokenType,
  TokenExtensions,
  DesignToken,
  TokenReference,
  TokenGroup,

  // Color types
  HSLColor,
  RGBColor,
  ColorToken,

  // Dimension types
  DimensionUnit,
  DimensionToken,

  // Typography types
  FontWeightToken,
  FontFamilyToken,
  TypographyToken,

  // Animation types
  DurationToken,
  CubicBezierToken,

  // Effect types
  ShadowToken,
  ShadowLayer,

  // Number type
  NumberToken,
} from './token';

export {
  TOKEN_TYPE,
  WCAG_LEVEL,
  DIMENSION_UNIT,
  // Type guards
  isDesignToken,
  isColorToken,
  isDimensionToken,
  isTokenReference,
} from './token';
