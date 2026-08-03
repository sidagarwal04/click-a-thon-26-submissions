/**
 * Themes - Tier 3
 * Theme compositions implementing the theme contract
 * @module tokens/themes
 */

import { darkTheme } from './dark';
import { lightTheme } from './light';

// Theme contract
export { createTheme, getThemeToken, createBrandedTheme } from './theme-contract';
export type {
  ThemeContract,
  ThemeMode,
  InteractiveState,
  ThemeTokenPath,
  BackgroundKey,
  TextKey,
  InteractiveVariant,
  BorderKey,
  FeedbackKey,
  ShadowKey,
  FocusKey,
  BrandConfig,
} from './theme-contract';

// Dark theme (primary)
export { darkTheme } from './dark';
export type { DarkTheme } from './dark';

// Light theme (secondary)
export { lightTheme } from './light';
export type { LightTheme } from './light';

/**
 * Default theme export
 * Dark theme is the primary/default theme
 */
export const defaultTheme = darkTheme;

/**
 * All available themes
 */
export const themes = {
  dark: darkTheme,
  light: lightTheme,
} as const;

/**
 * Theme names type
 */
export type ThemeName = keyof typeof themes;

/**
 * Helper to get a theme by name
 */
export function getTheme(name: ThemeName) {
  return themes[name];
}
