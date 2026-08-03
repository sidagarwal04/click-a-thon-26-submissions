import { workspaceRoot } from '@nx/devkit';
import { nxE2EPreset } from '@nx/playwright/preset';
import { defineConfig, devices } from '@playwright/test';

// For CI, you may want to set BASE_URL to the deployed application.
const baseURL = process.env['BASE_URL'] || 'http://localhost:4200';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  ...nxE2EPreset(__filename, { testDir: './src' }),
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    baseURL,
    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
  },
  /* Three servers, because the journeys run against the real stack.
   *
   * The JWKS server is what makes the rest honest: the API verifies every
   * bearer token against it, so identity resolution and RLS run exactly as
   * they do in production. Serving it with `http.server` over a directory is
   * cheaper and more predictable than running another application.
   *
   * Order matters only in that the API must find the JWKS when it first
   * verifies a token, not at boot — Playwright starts these in parallel and
   * waits for each url. */
  webServer: [
    {
      command: 'python3 -m http.server 9099 --directory .e2e/jwks',
      url: 'http://127.0.0.1:9099/.well-known/jwks.json',
      reuseExistingServer: !process.env['CI'],
      cwd: workspaceRoot,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      // The venv's interpreter directly, not `uv run`. A wrapper forks a child
      // that outlives the parent Playwright kills, and the orphan holds the
      // stdout it inherited — so `nx run-many` waits for an EOF that never
      // arrives and the job hangs instead of finishing. One process per server
      // is the whole fix; `stdout: 'ignore'` makes it belt and braces.
      command:
        '.venv/bin/python -m uvicorn zentra_api.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/health/ready',
      reuseExistingServer: !process.env['CI'],
      cwd: workspaceRoot,
      // The default 60s is not enough on a cold runner, where this is the
      // first `uv run` and the environment is resolved before uvicorn starts.
      timeout: 180_000,
      stdout: 'ignore',
      stderr: 'pipe',
      env: {
        CLERK_ISSUER: 'http://127.0.0.1:9099',
        FRONTEND_ORIGIN: baseURL,
      },
    },
    {
      // `vite preview` directly, not `nx run zentra-os:preview-e2e`. Playwright
      // is itself started by `nx run-many`, and a nested nx invocation contends
      // with the outer one for the daemon — the run hangs rather than failing,
      // which is the worst way for CI to break. The build is a separate CI step
      // for the same reason.
      // `node_modules/.bin/vite`, not `npx`: same orphaned-child problem.
      command:
        '../../node_modules/.bin/vite preview --mode e2e --outDir dist-e2e --port 4200 --strictPort',
      url: baseURL,
      reuseExistingServer: !process.env['CI'],
      cwd: `${workspaceRoot}/apps/zentra-os`,
      timeout: 120_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    // Uncomment for mobile browsers support
    /* {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    }, */

    // Uncomment for branded browsers
    /* {
      name: 'Microsoft Edge',
      use: { ...devices['Desktop Edge'], channel: 'msedge' },
    },
    {
      name: 'Google Chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    } */
  ],
});
