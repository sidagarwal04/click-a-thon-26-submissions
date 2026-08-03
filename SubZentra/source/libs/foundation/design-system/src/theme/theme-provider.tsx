/**
 * ThemeProvider - Central configuration point for the design system
 * @module theme/theme-provider
 */

import React, { useCallback, useContext, useEffect, useMemo } from 'react';

import type {
  DesignTokens,
  ThemeComponents,
  ThemeConfig,
  ThemeContextValue,
  ThemeProviderProps,
} from '../types';
import { defaultTheme, ThemeContext } from './theme-context';
import { mergeThemeConfigs } from './theme-resolver';

/**
 * Deep merges two theme configurations
 */
function deepMergeThemes(base: ThemeConfig, override: ThemeConfig): ThemeConfig {
  const mergedComponents: ThemeComponents = { ...base.components };

  // Merge each component's configuration
  for (const [componentName, componentConfig] of Object.entries(override.components)) {
    if (componentConfig) {
      const baseConfig = base.components[componentName];
      if (baseConfig) {
        mergedComponents[componentName] = mergeThemeConfigs(baseConfig, componentConfig);
      } else {
        mergedComponents[componentName] = componentConfig;
      }
    }
  }

  return {
    tokens: {
      ...base.tokens,
      ...override.tokens,
    },
    components: mergedComponents,
  };
}

/**
 * Applies design tokens as CSS custom properties
 */
function applyTokensToDOM(tokens: DesignTokens | undefined): void {
  if (typeof document === 'undefined' || !tokens) return;

  const root = document.documentElement;

  // Apply color tokens
  if (tokens.colors) {
    for (const [name, value] of Object.entries(tokens.colors)) {
      root.style.setProperty(`--color-${name}`, value);
    }
  }

  // Apply spacing tokens
  if (tokens.spacing) {
    for (const [name, value] of Object.entries(tokens.spacing)) {
      root.style.setProperty(`--spacing-${name}`, value);
    }
  }

  // Apply radii tokens
  if (tokens.radii) {
    for (const [name, value] of Object.entries(tokens.radii)) {
      root.style.setProperty(`--radius-${name}`, value);
    }
  }

  // Apply shadow tokens
  if (tokens.shadows) {
    for (const [name, value] of Object.entries(tokens.shadows)) {
      root.style.setProperty(`--shadow-${name}`, value);
    }
  }

  // Apply font size tokens
  if (tokens.fontSizes) {
    for (const [name, value] of Object.entries(tokens.fontSizes)) {
      root.style.setProperty(`--font-size-${name}`, value);
    }
  }

  // Apply duration tokens
  if (tokens.durations) {
    for (const [name, value] of Object.entries(tokens.durations)) {
      root.style.setProperty(`--duration-${name}`, value);
    }
  }
}

/**
 * ThemeProvider component
 *
 * Provides theme configuration to all child components through React context.
 * Supports nesting for component-level overrides with the `inherit` prop.
 *
 * @example
 * // Basic usage
 * <ThemeProvider theme={myTheme}>
 *   <App />
 * </ThemeProvider>
 *
 * @example
 * // With all options
 * <ThemeProvider
 *   theme={myTheme}
 *   analytics={{ onInteraction: trackEvent }}
 *   featureFlags={{ newFeature: true }}
 *   dir="rtl"
 *   locale="ar-SA"
 * >
 *   <App />
 * </ThemeProvider>
 *
 * @example
 * // Nested themes with inheritance
 * <ThemeProvider theme={globalTheme}>
 *   <ThemeProvider theme={sectionOverrides} inherit>
 *     {children}
 *   </ThemeProvider>
 * </ThemeProvider>
 */
export function ThemeProvider({
  theme,
  children,
  inherit = false,
  analytics,
  featureFlags,
  dir = 'ltr',
  locale,
  disableWrapper = false,
}: ThemeProviderProps): React.ReactElement {
  // Get parent context for inheritance
  const parentContext = useContext(ThemeContext);

  // Merge themes if inheriting
  const mergedTheme = useMemo(() => {
    if (inherit && parentContext.theme !== defaultTheme) {
      return deepMergeThemes(parentContext.theme, theme);
    }
    return theme;
  }, [inherit, parentContext.theme, theme]);

  // Apply tokens to DOM
  useEffect(() => {
    applyTokensToDOM(mergedTheme.tokens);
  }, [mergedTheme.tokens]);

  // Get component theme
  const getComponentTheme = useCallback(
    <K extends keyof ThemeComponents>(componentName: K) => {
      return mergedTheme.components[componentName];
    },
    [mergedTheme.components],
  );

  // Check feature flag
  const isFeatureEnabled = useCallback(
    (flagName: string): boolean => {
      // Check local flags first, then parent
      if (featureFlags?.[flagName] !== undefined) {
        return featureFlags[flagName];
      }
      if (inherit && parentContext.featureFlags) {
        return parentContext.isFeatureEnabled(flagName);
      }
      return false;
    },
    [featureFlags, inherit, parentContext],
  );

  // Merge analytics with parent
  const mergedAnalytics = useMemo(() => {
    if (!inherit || !parentContext.analytics) {
      return analytics;
    }
    return {
      ...parentContext.analytics,
      ...analytics,
    };
  }, [inherit, parentContext.analytics, analytics]);

  // Create context value
  const contextValue = useMemo<ThemeContextValue>(
    () => ({
      theme: mergedTheme,
      analytics: mergedAnalytics,
      featureFlags: inherit ? { ...parentContext.featureFlags, ...featureFlags } : featureFlags,
      dir,
      locale,
      getComponentTheme,
      isFeatureEnabled,
    }),
    [
      mergedTheme,
      mergedAnalytics,
      featureFlags,
      inherit,
      parentContext.featureFlags,
      dir,
      locale,
      getComponentTheme,
      isFeatureEnabled,
    ],
  );

  // Conditionally wrap in div with direction or render children directly
  return (
    <ThemeContext.Provider value={contextValue}>
      {disableWrapper ? (
        <>{children}</>
      ) : (
        <div dir={dir} data-theme-root="">
          {children}
        </div>
      )}
    </ThemeContext.Provider>
  );
}

ThemeProvider.displayName = 'OIThemeProvider';
