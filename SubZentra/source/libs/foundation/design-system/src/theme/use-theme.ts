/**
 * useTheme hook - consumes theme context and returns class resolvers
 * @module theme/use-theme
 */

import { useContext, useMemo } from 'react';

import type { ComponentThemeConfigStructure, ThemeComponents, UseThemeReturn } from '../types';
import { ThemeContext } from './theme-context';
import { createComponentResolvers, mergeThemeConfigs } from './theme-resolver';

/**
 * Hook to consume theme configuration for a component
 *
 * @example
 * const theme = useTheme('button', buttonDefaultTheme);
 * // Use in component:
 * <button className={theme.root({ intent, size, disabled })}>
 *   {startIcon && <span className={theme.startIcon({ size })}>{startIcon}</span>}
 *   {children}
 * </button>
 *
 * @param componentName - Name of the component in theme config
 * @param defaultConfig - Default theme configuration for the component
 * @returns Object with resolver functions for root and all slots
 */
export function useTheme<K extends keyof ThemeComponents>(
  componentName: K,
  defaultConfig: ComponentThemeConfigStructure,
): UseThemeReturn {
  const context = useContext(ThemeContext);
  const themeConfig = context?.theme?.components?.[componentName];

  // Merge default config with theme overrides
  const mergedConfig = useMemo(
    () => mergeThemeConfigs(defaultConfig, themeConfig),
    [defaultConfig, themeConfig],
  );

  // Create resolvers for all slots
  const resolvers = useMemo(() => createComponentResolvers(mergedConfig), [mergedConfig]);

  return resolvers as UseThemeReturn;
}

/**
 * Hook to get the current theme context value
 *
 * @returns Theme context value
 */
export function useThemeContext() {
  return useContext(ThemeContext);
}

/**
 * Hook to check if a feature flag is enabled
 *
 * @param flagName - Name of the feature flag
 * @returns true if the flag is enabled
 */
export function useFeatureFlag(flagName: string): boolean {
  const context = useContext(ThemeContext);
  return context.isFeatureEnabled(flagName);
}

/**
 * Hook to get the current direction (ltr/rtl)
 *
 * @returns Current direction
 */
export function useDirection() {
  const context = useContext(ThemeContext);
  return context.dir;
}

/**
 * Hook to get the current locale
 *
 * @returns Current locale or undefined
 */
export function useLocale() {
  const context = useContext(ThemeContext);
  return context.locale;
}

/**
 * Hook to get the analytics configuration
 *
 * @returns Analytics configuration or undefined
 */
export function useAnalytics() {
  const context = useContext(ThemeContext);
  return context.analytics;
}
