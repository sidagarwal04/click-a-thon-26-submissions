import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Reference all project configs using glob patterns
    projects: [
      'apps/*/vite.config.{mjs,js,ts,mts}',
      'libs/**/vite.config.{mjs,js,ts,mts}',
      'tools/*/vitest.config.{mjs,js,ts,mts}',
    ],
    // Global coverage configuration
    coverage: {
      provider: 'v8',
    },
  },
});
