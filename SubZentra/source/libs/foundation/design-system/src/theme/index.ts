/**
 * OpenZentra Design System - Theme
 * @module theme
 */

// Context
export { ThemeContext, defaultTheme } from './theme-context';

// Provider
export { ThemeProvider } from './theme-provider';

// Hooks
export {
  useTheme,
  useThemeContext,
  useFeatureFlag,
  useDirection,
  useLocale,
  useAnalytics,
} from './use-theme';

// Theme configuration factory
export {
  createThemeConfig,
  createEmptySlotConfig,
  createVariantConfig,
  createModifierConfig,
  type CreateThemeConfigOptions,
} from './create-theme-config';

// Resolver utilities
export {
  createSlotResolver,
  createComponentResolvers,
  mergeThemeConfigs,
  type SlotResolverProps,
} from './theme-resolver';
