import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { nxViteTsPaths } from '@nx/vite/plugins/nx-tsconfig-paths.plugin';
import type { StorybookConfig } from '@storybook/react-vite';
import { mergeConfig } from 'vite';

/**
 * Storybook configuration for the Foundation Design System library.
 *
 * This configuration provides:
 * - MDX documentation support
 * - Accessibility testing with addon-a11y
 * - Theme switching capabilities
 * - NX monorepo path resolution
 * - TypeScript documentation generation
 */
const config: StorybookConfig = {
  stories: ['../src/docs/**/*.mdx', '../src/**/*.stories.@(js|jsx|ts|tsx)'],

  addons: [
    '@storybook/addon-docs',
    '@storybook/addon-a11y',
    '@storybook/addon-themes',
    '@chromatic-com/storybook',
  ],

  framework: {
    name: getAbsolutePath('@storybook/react-vite'),
    options: {
      builder: {
        viteConfigPath: './vite.config.mts',
      },
    },
  },

  docs: {
    defaultName: 'Documentation',
  },

  typescript: {
    reactDocgen: 'react-docgen-typescript',
    check: true,
  },

  /**
   * Extends Vite configuration with NX TypeScript path mappings.
   * This enables proper module resolution across the monorepo.
   */
  viteFinal: async (viteConfig) =>
    mergeConfig(viteConfig, {
      plugins: [nxViteTsPaths()],
    }),
};

/**
 * Resolves the absolute path to a package's directory.
 * Used to ensure consistent resolution of Storybook framework packages.
 */
function getAbsolutePath(value: string): string {
  return dirname(fileURLToPath(import.meta.resolve(`${value}/package.json`)));
}

export default config;
