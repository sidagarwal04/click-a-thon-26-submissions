/**
 * The harness itself, before any journey depends on it.
 *
 * Every other spec assumes a signed-in browser reaching a real API under a
 * real Tenant. If that assumption breaks, those specs fail in confusing places
 * — a missing heading reads like a UI regression, not an auth one. So the
 * assumption is asserted here, once, in the terms it would break in.
 */

import AxeBuilder from '@axe-core/playwright';

import { expect, readTokens, test } from './support/authenticated';

test('an unauthenticated browser is not signed in by the harness', async ({
  anonymous,
}) => {
  await anonymous.goto('/');

  // The workspace must not render without a token. If this ever passes while
  // signed out, every role assertion in the suite is meaningless.
  await expect(
    anonymous.getByRole('heading', { name: /observatory|investigation/i }),
  ).toBeHidden();
});

test('an owner reaches the workspace with a real API identity', async ({
  owner,
}) => {
  const context = owner.waitForResponse(
    (response) =>
      response.url().includes('/v1/context') && response.status() === 200,
  );
  await owner.goto('/');

  // The API resolved a Tenant from the token — not the browser asserting it.
  const resolved = await (await context).json();
  expect(resolved.role).toBe('owner');
  expect(resolved.tenant_name).toBe('Forensic Observatory E2E');
});

for (const role of ['owner', 'admin', 'member', 'viewer'] as const) {
  test(`the API resolves ${role} from the token alone`, async ({
    page,
    baseURL,
  }) => {
    const { origin } = new URL(baseURL ?? 'http://localhost:4200');
    const tokens = readTokens();
    await page.context().addCookies([
      { name: 'zentra_e2e_role', value: role, url: origin },
      { name: 'zentra_e2e_token', value: tokens[role], url: origin },
    ]);

    const context = page.waitForResponse((response) =>
      response.url().includes('/v1/context'),
    );
    await page.goto('/');

    const resolved = await (await context).json();
    // Same Tenant every time: a role difference must be the only variable a
    // journey changes.
    expect(resolved.role).toBe(role);
    expect(resolved.tenant_name).toBe('Forensic Observatory E2E');
  });
}

test('the signed-in workspace has no accessibility violations', async ({
  owner,
}) => {
  await owner.goto('/');
  await owner.waitForResponse((response) =>
    response.url().includes('/v1/context'),
  );

  const accessibility = await new AxeBuilder({ page: owner })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});
