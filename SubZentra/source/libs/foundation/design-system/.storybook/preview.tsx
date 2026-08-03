import React, { useEffect } from 'react';

import type { Preview, ReactRenderer } from '@storybook/react';
import type { DecoratorFunction } from 'storybook/internal/types';

import { defaultTheme, ThemeProvider } from '../src/theme';
import { openInsightsDarkTheme, openInsightsLightTheme } from './theme';

import '../src/tokens/tokens.css';

/**
 * Custom viewport configurations for responsive testing.
 * These presets cover common device breakpoints used in enterprise applications.
 */
const VIEWPORT_PRESETS = {
  mobile: {
    name: 'Mobile',
    styles: {
      width: '375px',
      height: '667px',
    },
    type: 'mobile' as const,
  },
  mobileLarge: {
    name: 'Mobile Large',
    styles: {
      width: '414px',
      height: '896px',
    },
    type: 'mobile' as const,
  },
  tablet: {
    name: 'Tablet',
    styles: {
      width: '768px',
      height: '1024px',
    },
    type: 'tablet' as const,
  },
  tabletLandscape: {
    name: 'Tablet Landscape',
    styles: {
      width: '1024px',
      height: '768px',
    },
    type: 'tablet' as const,
  },
  desktop: {
    name: 'Desktop',
    styles: {
      width: '1280px',
      height: '800px',
    },
    type: 'desktop' as const,
  },
  desktopLarge: {
    name: 'Desktop Large',
    styles: {
      width: '1920px',
      height: '1080px',
    },
    type: 'desktop' as const,
  },
} as const;

/**
 * Theme configuration for backgrounds
 * Linear-inspired color values matching the design system
 */
const BACKGROUND_VALUES = {
  dark: {
    name: 'Dark (Default)',
    value: '#131316', // bg-layer-00
  },
  darkSurface: {
    name: 'Dark Surface',
    value: '#1A1A1E', // bg-layer-01
  },
  light: {
    name: 'Light',
    value: '#FAFAFA', // light bg-layer-00
  },
  lightSurface: {
    name: 'Light Surface',
    value: '#FFFFFF', // light bg-layer-01
  },
  brand: {
    name: 'Brand Accent',
    value: '#5E6AD2', // Linear accent
  },
};

/**
 * Theme mode decorator that applies the appropriate theme class
 * based on the selected background
 */
const ThemeModeDecorator: DecoratorFunction<ReactRenderer> = (Story, context) => {
  const background = context.globals?.backgrounds?.value;
  const isLightMode = background === '#FAFAFA' || background === '#FFFFFF';

  useEffect(() => {
    // Apply theme class to document for CSS variable scoping
    const root = document.documentElement;
    if (isLightMode) {
      root.classList.add('light');
      root.removeAttribute('data-theme');
      root.setAttribute('data-theme', 'light');
    } else {
      root.classList.remove('light');
      root.setAttribute('data-theme', 'dark');
    }

    return () => {
      root.classList.remove('light');
      root.removeAttribute('data-theme');
    };
  }, [isLightMode]);

  return <Story />;
};

/**
 * Theme provider decorator that wraps all stories with the design system's ThemeProvider.
 * This ensures consistent styling and token availability across all component stories.
 */
const withThemeProvider: DecoratorFunction<ReactRenderer> = (Story) => (
  <ThemeProvider theme={defaultTheme}>
    <Story />
  </ThemeProvider>
);

/**
 * Storybook preview configuration for the Foundation Design System.
 *
 * Features:
 * - Dark mode as default (Linear-inspired)
 * - Accessibility testing with axe-core integration
 * - Responsive viewport presets for mobile, tablet, and desktop
 * - Background color options matching design system themes
 * - Automatic documentation generation
 * - Theme provider integration
 */
const preview: Preview = {
  parameters: {
    /**
     * Accessibility testing configuration using axe-core.
     * Rules can be customized per-story if needed.
     */
    a11y: {
      element: '#storybook-root',
      config: {
        rules: [
          { id: 'color-contrast', enabled: true },
          { id: 'landmark-one-main', enabled: false },
          { id: 'region', enabled: false },
        ],
      },
    },

    /**
     * Control panel configuration with smart type matchers.
     */
    controls: {
      expanded: true,
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
      sort: 'requiredFirst',
    },

    /**
     * Background options for testing component appearance.
     * Dark mode is the default, matching Linear's design language.
     */
    backgrounds: {
      default: 'Dark (Default)',
      values: Object.values(BACKGROUND_VALUES),
    },

    /**
     * Viewport configuration for responsive testing.
     */
    viewport: {
      viewports: VIEWPORT_PRESETS,
      defaultViewport: 'desktop',
    },

    /**
     * Documentation configuration.
     */
    docs: {
      toc: {
        title: 'On this page',
        headingSelector: 'h2, h3',
      },
    },

    /**
     * Default layout for stories.
     */
    layout: 'centered',

    /**
     * Actions configuration for event logging.
     * Note: Using explicit fn() from storybook/test for action props
     * is recommended over argTypesRegex for better compatibility.
     */
    actions: {
      disable: false,
    },

    /**
     * Theme configuration for docs pages
     */
    darkMode: {
      dark: openInsightsDarkTheme,
      light: openInsightsLightTheme,
      current: 'dark',
      stylePreview: true,
    },
  },

  /**
   * Global decorators applied to all stories.
   * Order matters: ThemeModeDecorator should run after withThemeProvider
   */
  decorators: [ThemeModeDecorator, withThemeProvider],

  /**
   * Global tags for all stories.
   */
  tags: ['autodocs'],

  /**
   * Initial global values.
   * Sets dark mode as the default background.
   */
  initialGlobals: {
    backgrounds: { value: '#131316' }, // Dark mode default
  },
};

export default preview;
