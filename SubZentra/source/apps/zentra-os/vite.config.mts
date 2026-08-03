/// <reference types='vitest' />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig(({ mode }) => ({
  root: import.meta.dirname,
  cacheDir: '../../node_modules/.vite/apps/zentra-os',
  server: {
    port: 4200,
    host: 'localhost',
  },
  preview: {
    port: 4200,
    host: 'localhost',
  },
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: [
      // @thesysai/genui-sdk's installed version stopped exporting this
      // subpath in its package.json `exports` map, even though the file is
      // still physically shipped in `dist/`. Aliasing straight to the file
      // bypasses the export-map restriction rather than the file itself.
      {
        find: '@thesysai/genui-sdk/dist/genui-sdk.css',
        replacement: fileURLToPath(
          new URL(
            './node_modules/@thesysai/genui-sdk/dist/genui-sdk.css',
            import.meta.url,
          ),
        ),
      },
      // Browser journeys run against a real API, a real JWKS and real RLS;
      // the one thing they cannot have is a real Clerk session. Swapping the
      // identity provider here — and only in `e2e` mode — keeps the bypass
      // out of every build that is not a test run. A provider added inside
      // foundation-auth would ship instead, and a shipped auth bypass is one
      // somebody reaches.
      ...(mode === 'e2e'
        ? // Exact matches, not prefixes. An object alias matches on prefix and
          // takes the first hit, so a bare `@open-zentra/foundation-auth` entry
          // would rewrite `.../foundation-auth/clerk` into
          // `auth-stub.tsx/clerk`. The array form with an anchored regex makes
          // each specifier stand alone.
          [
            '@open-zentra/foundation-auth',
            '@open-zentra/foundation-auth/clerk',
            '@open-zentra/foundation-authz/clerk',
            '@clerk/clerk-react',
          ].map((specifier) => ({
            find: new RegExp(`^${specifier.replace(/[/\\-]/g, '\\$&')}$`),
            replacement: fileURLToPath(
              new URL('./src/e2e/auth-stub.tsx', import.meta.url),
            ),
          }))
        : []),
    ],
  },
  // DuckDB-WASM contains WASM + workers that shouldn't be pre-bundled
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
  build: {
    outDir: './dist',
    emptyOutDir: true,
    reportCompressedSize: true,
    commonjsOptions: {
      transformMixedEsModules: true,
    },
  },
  test: {
    name: 'zentra-os',
    watch: false,
    globals: true,
    environment: 'jsdom',
    include: ['{src,tests}/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    reporters: ['default'],
    coverage: {
      reportsDirectory: './test-output/vitest/coverage',
      provider: 'v8' as const,
    },
  },
}));
