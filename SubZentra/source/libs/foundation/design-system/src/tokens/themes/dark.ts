/**
 * Dark Theme - Primary Theme
 *
 * Design principles:
 * - Green-tinted charcoal canvas, near black
 * - Signal lime as the single interactive accent
 * - Violet reserved for navigation and agent surfaces
 * - Subtle layer elevation
 * - High contrast text hierarchy
 *
 * @module tokens/themes/dark
 */

import type { ThemeContract } from './theme-contract';
import { createTheme } from './theme-contract';

/**
 * Dark theme implementing the ThemeContract
 */
export const darkTheme = createTheme({
  name: 'Open Zentra Dark',
  mode: 'dark',

  colors: {
    background: {
      // Layer system: darker = deeper
      layer00: 'hsl(140 8% 4%)', // Deepest - canvas
      layer01: 'hsl(140 7% 6%)', // Default surface
      layer02: 'hsl(140 6% 9%)', // Elevated
      layer03: 'hsl(140 6% 12%)', // Highest - modals
      overlay: 'hsla(140 10% 2% / 0.82)', // Backdrop
    },

    text: {
      // Text hierarchy: lighter = more emphasis
      highlight: 'hsl(96 14% 96%)', // Maximum
      primary: 'hsl(96 10% 92%)', // High contrast
      secondary: 'hsl(140 5% 70%)', // Reduced
      tertiary: 'hsl(140 5% 57%)', // Placeholders
      muted: 'hsl(140 5% 40%)', // Disabled
      inverted: 'hsl(140 10% 4%)', // On colored BG
    },

    interactive: {
      primary: {
        resting: 'hsl(88 100% 70%)', // Signal lime
        hovered: 'hsl(88 100% 78%)', // Lighter on hover
        pressed: 'hsl(88 92% 63%)', // Darker on press
        disabled: 'hsl(88 20% 40%)', // Desaturated
      },
      secondary: {
        resting: 'hsl(140 6% 14%)',
        hovered: 'hsl(140 6% 18%)',
        pressed: 'hsl(140 6% 22%)',
        disabled: 'hsl(140 6% 12%)',
      },
      tertiary: {
        resting: 'transparent',
        hovered: 'hsl(140 6% 12%)',
        pressed: 'hsl(140 6% 16%)',
        disabled: 'transparent',
      },
      destructive: {
        resting: 'hsl(0 74% 54%)',
        hovered: 'hsl(0 78% 62%)',
        pressed: 'hsl(0 74% 48%)',
        disabled: 'hsl(0 30% 40%)',
      },
      smart: {
        resting: 'hsl(263 83% 58%)',
        hovered: 'hsl(263 83% 64%)',
        pressed: 'hsl(263 83% 52%)',
        disabled: 'hsl(263 40% 45%)',
      },
    },

    border: {
      default: 'hsl(140 6% 16%)',
      subtle: 'hsl(140 6% 12%)',
      emphasis: 'hsl(140 6% 24%)',
      focus: 'hsl(88 100% 70%)',
    },

    feedback: {
      success: 'hsl(92 72% 60%)',
      warning: 'hsl(45 90% 60%)',
      error: 'hsl(0 78% 63%)',
      info: 'hsl(210 80% 65%)',
    },
  },

  effects: {
    shadow: {
      depth01: '0 0 2px 0 hsla(140 10% 2% / 0.4), 0 2px 4px 0 hsla(140 10% 2% / 0.3)',
      depth02: '0 2px 12px 0 hsla(140 10% 2% / 0.45)',
      depth03: '0 0 6px 1px hsla(140 10% 2% / 0.3), 0 2px 24px 0 hsla(140 10% 2% / 0.4)',
      depth04: '0 4px 32px 0 hsla(140 10% 2% / 0.55), 0 16px 48px 0 hsla(140 10% 2% / 0.45)',
    },
    focus: {
      ring: '0 0 0 2px hsla(88 100% 70% / 0.35)',
      ringOffset: '0 0 0 4px hsla(88 100% 70% / 0.12)',
    },
  },
} as const satisfies ThemeContract);

/**
 * Export theme type for external use
 */
export type DarkTheme = typeof darkTheme;
