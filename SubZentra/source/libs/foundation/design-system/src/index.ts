/**
 * OpenZentra Design System
 *
 * A fully extensible, enterprise-grade design system built with
 * Base UI primitives, Tailwind CSS, and TypeScript.
 *
 * @packageDocumentation
 */

// ============================================
// Types
// ============================================
export * from './types';

// ============================================
// Theme
// ============================================
export {
  ThemeProvider,
  ThemeContext,
  defaultTheme,
  useTheme,
  useThemeContext,
  useFeatureFlag,
  useDirection,
  useLocale,
  useAnalytics,
  createThemeConfig,
  createEmptySlotConfig,
  createVariantConfig,
  createModifierConfig,
  createSlotResolver,
  createComponentResolvers,
  mergeThemeConfigs,
} from './theme';
export type { CreateThemeConfigOptions, SlotResolverProps } from './theme';

// ============================================
// Utils
// ============================================
export {
  cn,
  slotOzid,
  isValidOzid,
  parseSlotOzid,
  createOzidGenerator,
  OZID_SEPARATOR,
  normalizeSlot,
  normalizeSlots,
  getSlotNames,
  getOverridableSlotNames,
  isReactNode,
  isSlotConfig,
  getSlotChildren,
  getSlotComponent,
  getSlotClassName,
  generateA11yId,
  resetA11yIdCounter,
  visuallyHiddenStyles,
  visuallyHiddenClasses,
  shouldShowFocusRing,
  A11yKeys,
  isKey,
  focusableSelector,
  getFocusableElements,
  trapFocus,
  announceToScreenReader,
  getDisabledState,
  getDisplayName,
  createPolymorphicComponent,
} from './utils';
export type {
  ClassValue,
  WithOzid,
  WithBaseOzid,
  A11yKey,
  FocusableElement,
  DisableableProps,
  ExtractPolymorphicProps,
  ExtractPolymorphicRef,
} from './utils';

// ============================================
// Primitives
// ============================================
export { Slot, VisuallyHidden } from './primitives';
export type {
  SlotProps,
  SlotComponent,
  SlotOwnProps,
  SlotDefaultElement,
  VisuallyHiddenProps,
} from './primitives';

// ============================================
// Components
// ============================================
export * from './components';

// ============================================
// Tokens (re-export for programmatic access)
// ============================================
export * from './tokens';
