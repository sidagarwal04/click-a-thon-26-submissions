/**
 * Token Utilities - Public API
 * @module tokens/utils
 */

// Color utilities
export {
  DEFAULT_COLOR_STEPS,
  createColorToken,
  createColorTokenWithAlpha,
  generateColorScale,
  hslToRgb,
  rgbToHsl,
  hslToHex,
  hexToHsl,
  adjustLightness,
  adjustSaturation,
  toHslString,
  mixColors,
} from './color-utils';
export type { ColorStep } from './color-utils';

// Contrast checker utilities
export {
  getRelativeLuminance,
  getRelativeLuminanceFromHSL,
  calculateContrastRatio,
  validateContrast,
  suggestLightnessAdjustment,
  batchValidateContrast,
  isLightColor,
  getOptimalTextColor,
} from './contrast-checker';
export type { WCAGLevel, ContrastResult, ContrastOptions } from './contrast-checker';

// CSS generator utilities
export {
  generateCSSVariables,
  generateThemeCSS,
  generateMultiThemeCSS,
  cssVar,
  cssVarWithFallback,
  generateTailwindTheme,
  generateReducedMotionCSS,
  generateFileHeader,
} from './css-generator';
export type { CSSGeneratorOptions } from './css-generator';
