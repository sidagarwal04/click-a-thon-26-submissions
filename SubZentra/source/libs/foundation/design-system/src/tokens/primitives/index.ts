/**
 * Primitives - Tier 1 Tokens
 * Raw design values that form the foundation of the design system
 * @module tokens/primitives
 */

// Color primitives
export {
  COLOR_DEFINITIONS,
  colorPrimitives,
  accentScale,
  neutralScale,
  alertScale,
  warningScale,
  successScale,
  smartScale,
  infoScale,
  staticColors,
  getScaleColor,
  colorVar,
} from './colors';
export type { ColorDefinition, ColorScaleName, NeutralStep, AccentStep } from './colors';

// Typography primitives
export {
  fontWeights,
  fontFamilies,
  textStyles,
  typographyPrimitives,
  fontWeightVar,
  fontFamilyVar,
} from './typography';
export type { TextStyleDefinition, TextStyleKey, FontWeightKey, FontFamilyKey } from './typography';

// Spacing primitives
export {
  PHI,
  PHI_INVERSE,
  PHI_POWERS,
  spacingPrimitives,
  standardSpacing,
  radiusPrimitives,
  spacingVar,
  radiusVar,
  calculatePhiSpacing,
} from './spacing';
export type { SpacingKey, StandardSpacingKey, RadiusKey } from './spacing';

// Motion primitives
export {
  durations,
  easings,
  transitions,
  animations,
  motionPrimitives,
  durationVar,
  easingVar,
  createTransition,
  createTransitions,
} from './motion';
export type { DurationKey, EasingKey, TransitionKey, AnimationKey } from './motion';
