/**
 * Theme-aware render utility for testing
 * @module test/render-with-theme
 */

import React from 'react';

import { render, type RenderOptions, type RenderResult } from '@testing-library/react';

import { ThemeProvider } from '../theme';
import type { ThemeConfig, ThemeProviderProps } from '../types';

/**
 * Default empty theme for testing
 */
const defaultTestTheme: ThemeConfig = {
  components: {},
};

/**
 * Options for renderWithTheme
 */
export interface RenderWithThemeOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Theme configuration */
  theme?: ThemeConfig;
  /** Additional ThemeProvider props */
  themeProps?: Partial<Omit<ThemeProviderProps, 'theme' | 'children'>>;
}

/**
 * Renders a component wrapped with ThemeProvider for testing
 *
 * @example
 * const { getByRole } = renderWithTheme(<Button>Click</Button>, {
 *   theme: { components: { button: { root: { base: 'test-class' } } } },
 * });
 *
 * @param ui - Component to render
 * @param options - Render options including theme
 * @returns Render result with all Testing Library queries
 */
export function renderWithTheme(
  ui: React.ReactElement,
  options: RenderWithThemeOptions = {},
): RenderResult {
  const { theme = defaultTestTheme, themeProps = {}, ...renderOptions } = options;

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <ThemeProvider theme={theme} {...themeProps}>
        {children}
      </ThemeProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

/**
 * Creates a custom render function with a specific theme
 *
 * @param defaultTheme - Default theme for all renders
 * @returns Custom render function
 */
export function createThemeRenderer(defaultTheme: ThemeConfig) {
  return (ui: React.ReactElement, options: RenderWithThemeOptions = {}) => {
    return renderWithTheme(ui, {
      theme: defaultTheme,
      ...options,
    });
  };
}
