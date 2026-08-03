import type { ThemeVars } from 'storybook/theming';
import { create } from 'storybook/theming/create';

/**
 * Linear-inspired dark theme for Storybook
 *
 * Design philosophy:
 * - Dark-first aesthetic matching the design system
 * - Mercury White (#F4F5F8) for highlights
 * - Nordic Gray (#222326) inspired backgrounds
 * - Desaturated indigo-blue accent (#5E6AD2)
 * - Minimal, clean UI with subtle depth
 */
export const openInsightsDarkTheme: ThemeVars = create({
  base: 'dark',

  // Brand
  brandTitle: 'Open Zentra Design System',
  brandUrl: '/',
  brandTarget: '_self',

  // Typography - Inter variable font like Linear
  fontBase:
    '"Inter var", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
  fontCode: '"JetBrains Mono", "SF Mono", "Fira Code", Consolas, monospace',

  // Linear accent colors
  colorPrimary: '#5E6AD2',
  colorSecondary: '#8B8FE8',

  // UI backgrounds - layered system
  appBg: '#131316', // layer00
  appContentBg: '#1A1A1E', // layer01
  appPreviewBg: '#1A1A1E', // layer01
  appBorderColor: '#2D2D32',
  appBorderRadius: 8,

  // Text hierarchy
  textColor: '#F4F5F8', // Mercury White - highlight
  textInverseColor: '#131316',
  textMutedColor: '#8B8D98', // secondary text

  // Toolbar
  barTextColor: '#8B8D98',
  barSelectedColor: '#5E6AD2',
  barHoverColor: '#F4F5F8',
  barBg: '#1A1A1E',

  // Forms
  inputBg: '#222226',
  inputBorder: '#3D3D42',
  inputTextColor: '#F4F5F8',
  inputBorderRadius: 6,

  // Buttons
  buttonBg: '#2D2D32',
  buttonBorder: '#3D3D42',

  // Booleans
  booleanBg: '#2D2D32',
  booleanSelectedBg: '#5E6AD2',
});

/**
 * Linear-inspired light theme for Storybook
 *
 * Secondary theme with inverted color values
 * maintaining the same design principles.
 */
export const openInsightsLightTheme: ThemeVars = create({
  base: 'light',

  // Brand
  brandTitle: 'Open Zentra Design System',
  brandUrl: '/',
  brandTarget: '_self',

  // Typography
  fontBase:
    '"Inter var", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
  fontCode: '"JetBrains Mono", "SF Mono", "Fira Code", Consolas, monospace',

  // Accent colors (slightly darker for light mode)
  colorPrimary: '#5E6AD2',
  colorSecondary: '#4850B8',

  // UI backgrounds
  appBg: '#FAFAFA',
  appContentBg: '#FFFFFF',
  appPreviewBg: '#FFFFFF',
  appBorderColor: '#E8E8EA',
  appBorderRadius: 8,

  // Text hierarchy
  textColor: '#131316',
  textInverseColor: '#F4F5F8',
  textMutedColor: '#6B6B74',

  // Toolbar
  barTextColor: '#6B6B74',
  barSelectedColor: '#5E6AD2',
  barHoverColor: '#131316',
  barBg: '#FFFFFF',

  // Forms
  inputBg: '#FFFFFF',
  inputBorder: '#E8E8EA',
  inputTextColor: '#131316',
  inputBorderRadius: 6,

  // Buttons
  buttonBg: '#F4F4F5',
  buttonBorder: '#E8E8EA',

  // Booleans
  booleanBg: '#E8E8EA',
  booleanSelectedBg: '#5E6AD2',
});

/**
 * Default theme export
 * Dark theme is the primary theme
 */
export const openInsightsTheme: ThemeVars = openInsightsDarkTheme;
