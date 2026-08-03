/**
 * Theme context for the OpenZentra Design System
 * @module theme/theme-context
 */

import { createContext } from 'react';

import type { ThemeConfig, ThemeContextValue } from '../types';

/**
 * Default empty theme configuration
 */
export const defaultTheme: ThemeConfig = {
  components: {},
};

/**
 * Default theme context value
 */
const defaultContextValue: ThemeContextValue = {
  theme: defaultTheme,
  dir: 'ltr',
  getComponentTheme: () => undefined,
  isFeatureEnabled: () => false,
};

/**
 * React context for theme distribution
 */
export const ThemeContext = createContext<ThemeContextValue>(defaultContextValue);

ThemeContext.displayName = 'OIThemeContext';
