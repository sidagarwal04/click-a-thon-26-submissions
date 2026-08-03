/**
 * Signing in, as a fixture.
 *
 * `test.extend` rather than a helper each spec remembers to call: a journey
 * that forgot would silently run signed-out and assert the setup screen, which
 * looks like a pass. Asking for the `owner` fixture is the only way to get a
 * page, so there is no signed-out-by-accident path.
 *
 * The tokens are minted by `tools/e2e/prepare.py` and read from `.e2e/`. They
 * are real RS256 tokens the API verifies against a real JWKS — the fixture
 * only decides which one the browser carries.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { test as base, type Page } from '@playwright/test';

export type Role = 'owner' | 'admin' | 'member' | 'viewer';

// `__dirname`, not `import.meta.url`: Playwright loads these specs as
// CommonJS, where `import.meta` is a syntax error rather than a runtime one —
// so the whole file fails to load and no test reports at all.
const tokensPath = resolve(__dirname, '../../../../.e2e/tokens.json');

export const readTokens = (): Record<Role, string> => {
  try {
    return JSON.parse(readFileSync(tokensPath, 'utf8')) as Record<Role, string>;
  } catch {
    throw new Error(
      `No e2e tokens at ${tokensPath}. Run: uv run python tools/e2e/prepare.py`,
    );
  }
};

const signIn = async (page: Page, role: Role, baseURL: string) => {
  const token = readTokens()[role];
  if (!token) {
    throw new Error(`No token minted for role "${role}"`);
  }
  const { origin } = new URL(baseURL);
  await page.context().addCookies([
    { name: 'zentra_e2e_role', value: role, url: origin },
    { name: 'zentra_e2e_token', value: token, url: origin },
  ]);
};

interface RoleFixtures {
  owner: Page;
  admin: Page;
  member: Page;
  viewer: Page;
  /** A page with no token, for asserting the signed-out surface. */
  anonymous: Page;
}

const roleFixture =
  (role: Role) =>
  async (
    { page, baseURL }: { page: Page; baseURL?: string },
    use: (page: Page) => Promise<void>,
  ) => {
    await signIn(page, role, baseURL ?? 'http://localhost:4200');
    await use(page);
  };

export const test = base.extend<RoleFixtures>({
  owner: roleFixture('owner'),
  admin: roleFixture('admin'),
  member: roleFixture('member'),
  viewer: roleFixture('viewer'),
  anonymous: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';
