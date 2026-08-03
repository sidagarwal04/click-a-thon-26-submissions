/**
 * Semantic Tokens - Tier 2
 * Usage-based tokens that reference primitives
 * @module tokens/semantic
 */

// Background tokens
export {
  backgroundLayers,
  backgroundInteractive,
  backgroundNavigation,
  backgroundInput,
  backgroundFeedback,
  backgroundMisc,
  backgroundTokens,
} from './backgrounds';
export type {
  InteractiveStateTokens,
  BackgroundLayerKey,
  BackgroundInteractiveKey,
  BackgroundFeedbackKey,
} from './backgrounds';

// Border tokens
export {
  borderColors,
  borderInteractive,
  borderInput,
  borderNavigation,
  borderFeedback,
  borderSeparator,
  borderWidths,
  borderStyles,
  borderTokens,
} from './borders';
export type { BorderColorKey, BorderWidthKey, BorderStyleKey } from './borders';

// Text tokens
export {
  textColors,
  textStatic,
  textInteractive,
  textLink,
  textNavigation,
  textInput,
  textFeedback,
  textAccent,
  textCode,
  textTokens,
} from './text';
export type { TextColorKey, TextFeedbackKey } from './text';

// Effect tokens
export {
  shadowDepth,
  shadowInteractive,
  focusRing,
  shadowComponent,
  glowEffects,
  effectTokens,
  getShadowValue,
} from './effects';
export type { ShadowDepthKey, ShadowInteractiveKey, FocusRingKey } from './effects';
