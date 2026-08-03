/**
 * Light Theme - Secondary Theme
 * Linear-inspired light theme implementation
 *
 * Design principles:
 * - Inverted layer values (lighter = deeper)
 * - Adjusted interactive states for light backgrounds
 * - Maintained color semantics
 *
 * @module tokens/themes/light
 */

import type { ThemeContract } from './theme-contract';
import { createTheme } from './theme-contract';

/**
 * Light theme implementing the ThemeContract
 */
export const lightTheme = createTheme({
  name: 'Open Zentra Light',
  mode: 'light',

  colors: {
    background: {
      // Layer system: lighter = deeper (inverted)
      layer00: 'hsl(140 6% 98%)', // Deepest - canvas
      layer01: 'hsl(140 6% 100%)', // Default surface (white)
      layer02: 'hsl(140 6% 100%)', // Elevated (same as layer01)
      layer03: 'hsl(140 6% 100%)', // Highest - modals
      overlay: 'hsla(140 8% 8% / 0.4)', // Backdrop (semi-transparent)
    },

    text: {
      // Text hierarchy: darker = more emphasis
      highlight: 'hsl(140 6% 8%)', // Maximum emphasis
      primary: 'hsl(140 6% 12%)', // High contrast
      secondary: 'hsl(140 6% 36%)', // Reduced
      tertiary: 'hsl(140 6% 48%)', // Placeholders
      muted: 'hsl(140 6% 62%)', // Disabled
      inverted: 'hsl(140 6% 96%)', // On colored BG
    },

    interactive: {
      primary: {
        resting: 'hsl(88 72% 28%)', // Slightly darker for light mode
        hovered: 'hsl(88 72% 24%)', // Darker on hover
        pressed: 'hsl(88 72% 20%)', // Even darker on press
        disabled: 'hsl(88 20% 70%)', // Desaturated, lighter
      },
      secondary: {
        resting: 'hsl(140 6% 100%)', // White
        hovered: 'hsl(140 6% 96%)', // Light gray
        pressed: 'hsl(140 6% 92%)', // Darker gray
        disabled: 'hsl(140 6% 96%)', // Light gray
      },
      tertiary: {
        resting: 'transparent',
        hovered: 'hsl(140 6% 96%)',
        pressed: 'hsl(140 6% 94%)',
        disabled: 'transparent',
      },
      destructive: {
        resting: 'hsl(0 74% 46%)',
        hovered: 'hsl(0 74% 42%)',
        pressed: 'hsl(0 74% 38%)',
        disabled: 'hsl(0 30% 70%)',
      },
      smart: {
        resting: 'hsl(263 83% 52%)',
        hovered: 'hsl(263 83% 46%)',
        pressed: 'hsl(263 83% 42%)',
        disabled: 'hsl(263 40% 75%)',
      },
    },

    border: {
      default: 'hsl(140 6% 92%)',
      subtle: 'hsl(140 6% 94%)',
      emphasis: 'hsl(140 6% 88%)',
      focus: 'hsl(88 72% 28%)',
    },

    feedback: {
      success: 'hsl(92 66% 32%)', // Darker for light mode
      warning: 'hsl(45 82% 38%)',
      error: 'hsl(0 74% 46%)',
      info: 'hsl(210 80% 45%)',
    },
  },

  effects: {
    shadow: {
      // Lighter shadows for light mode
      depth01: '0 0 2px 0 hsla(140 8% 8% / 0.05), 0 2px 4px 0 hsla(140 8% 8% / 0.03)',
      depth02: '0 2px 12px 0 hsla(140 8% 8% / 0.08)',
      depth03: '0 0 6px 1px hsla(140 8% 8% / 0.03), 0 2px 24px 0 hsla(140 8% 8% / 0.06)',
      depth04: '0 4px 32px 0 hsla(140 8% 8% / 0.12), 0 16px 48px 0 hsla(140 8% 8% / 0.08)',
    },
    focus: {
      ring: '0 0 0 2px hsla(88 72% 28% / 0.2)',
      ringOffset: '0 0 0 4px hsla(88 72% 28% / 0.1)',
    },
  },
} as const satisfies ThemeContract);

/**
 * Export theme type for external use
 */
export type LightTheme = typeof lightTheme;
