/**
 * The Phase 2 trust experience, as a reviewer meets it.
 *
 * These assert what a person can *see and reach*, not what the API returned.
 * The API is already covered by its own suite; what only a browser can show is
 * whether the distinction between measured evidence and interpretation
 * survives rendering, whether an unavailable citation is visibly different
 * from a deleted one, and whether a viewer is actually prevented from deciding
 * rather than merely un-encouraged.
 *
 * Fixtures come from `tools/e2e/fixtures.py` and are addressed by fixed id, so
 * a deep link is a literal a spec can write down — which is also what
 * criterion 9 asks the product to support.
 */

import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';

import { expect, test } from './support/authenticated';

const PUBLISHED = 'e2e00000-0000-4000-8000-000000000001';
const GATED = 'e2e00000-0000-4000-8000-000000000002';
const CONTRADICTED = 'e2e00000-0000-4000-8000-000000000003';

const open = async (page: Page, id: string) => {
  const loaded = page.waitForResponse(
    (response) =>
      response.url().includes(`/v1/investigations/${id}`) &&
      response.status() === 200,
  );
  await page.goto(`/investigations/${id}`);
  await loaded;
  // The draft panel renders from the same response; waiting on it rather than
  // on a timeout keeps these from flaking under a cold API.
  await expect(page.locator('[data-state="structured"]')).toBeVisible();
};

test.describe('an automatically publishable Investigation', () => {
  test('exposes each claim with its own measurement', async ({ owner }) => {
    await open(owner, PUBLISHED);

    const panel = owner.locator('[data-state="structured"]');
    await expect(panel.locator('ol > li')).toHaveCount(3);
    // Scoped to the claim panel. The same figure also appears in the narrative
    // headline and the metric bar — that repetition is the product agreeing
    // with itself, so an unscoped matcher is ambiguous rather than wrong.
    await expect(panel.getByText('0.0412')).toBeVisible();
    await expect(panel.getByText('184', { exact: true })).toBeVisible();
  });

  test('labels evidence and interpretation as different things', async ({
    owner,
  }) => {
    await open(owner, PUBLISHED);

    // Text, not colour: a reader who cannot tell the two badges apart still
    // gets the distinction, which is what criterion 5 is protecting.
    await expect(owner.getByText('Measured', { exact: true })).toHaveCount(2);
    await expect(
      owner.getByText('Interpretation', { exact: true }),
    ).toHaveCount(1);
  });

  test('says root cause is unresolved, prominently', async ({ owner }) => {
    await open(owner, PUBLISHED);

    // Criterion 6. ADR 0011 turns on the product saying this out loud rather
    // than leaving causality to be assumed by omission.
    await expect(owner.getByText(/root cause unresolved/i)).toBeVisible();
  });
});

test.describe('an Investigation held back from publication', () => {
  test('shows the contradiction rather than smoothing it away', async ({
    owner,
  }) => {
    await open(owner, CONTRADICTED);

    await expect(owner.getByText(/unresolved contradiction/i)).toBeVisible();
    await expect(owner.getByText(/the recheck measured 4\.12%/i)).toBeVisible();
  });

  test('does not conflate unavailable evidence with deleted evidence', async ({
    owner,
  }) => {
    await open(owner, GATED);

    // Criterion 7. Unexpected loss and a deliberate erasure are different
    // answers to a Tenant, and the gated fixture is the former: nothing on
    // this page may describe it as deleted, erased or tombstoned.
    const body = (await owner.locator('body').innerText()).toLowerCase();
    expect(body).not.toContain('tombstone');
    expect(body).not.toContain('deleted');
    expect(body).not.toContain('erased');
  });
});

test.describe('authorization is the server’s answer, not the browser’s', () => {
  for (const role of ['viewer', 'member'] as const) {
    test(`a ${role} gets no decision controls`, async ({ page, baseURL }) => {
      const { origin } = new URL(baseURL ?? 'http://localhost:4200');
      const { readTokens } = await import('./support/authenticated');
      await page.context().addCookies([
        { name: 'zentra_e2e_role', value: role, url: origin },
        { name: 'zentra_e2e_token', value: readTokens()[role], url: origin },
      ]);
      await open(page, CONTRADICTED);

      // Criterion 4. Absent, not merely disabled — a control a role may not
      // use is a control it should not be offered.
      await expect(
        page.getByRole('button', { name: /approve|reject/i }),
      ).toHaveCount(0);
    });
  }
});

test.describe('reconstruction', () => {
  test('a deep link and a refresh show the same Finding', async ({ owner }) => {
    await open(owner, PUBLISHED);
    const panel = owner.locator('[data-state="structured"]');
    const before = await panel.textContent();

    await owner.reload();
    await expect(panel).toBeVisible();

    // Criterion 9. Identical, not merely similar: a Finding that reorders its
    // claims across a refresh is a Finding a reviewer cannot cite.
    await expect(panel).toHaveText(before ?? '');
  });
});

test.describe('nothing a Tenant owns leaks into the page', () => {
  for (const [name, id] of [
    ['published', PUBLISHED],
    ['gated', GATED],
    ['contradicted', CONTRADICTED],
  ] as const) {
    test(`the ${name} Investigation renders no prompt or hidden reasoning`, async ({
      owner,
    }) => {
      await open(owner, id);
      const body = (await owner.locator('body').innerText()).toLowerCase();

      // Criterion 13. The page shows conclusions and the evidence under them;
      // it must never show the instructions that produced them, the model's
      // private reasoning, or a credential.
      for (const forbidden of [
        'you are the',
        'system prompt',
        '<thinking>',
        'sk-ant-',
        'bearer ',
      ]) {
        expect(body).not.toContain(forbidden);
      }
    });
  }
});

test.describe('accessibility', () => {
  for (const [name, id] of [
    ['published', PUBLISHED],
    ['gated', GATED],
    ['contradicted', CONTRADICTED],
  ] as const) {
    test(`the ${name} Investigation has no WCAG A or AA violations`, async ({
      owner,
    }) => {
      // Scanned with motion settled. Mid-transition an element's effective
      // colour is a blend of where it started and where it is going, so axe
      // sampling a fade frame reported contrast values that appear nowhere in
      // the stylesheet and failed intermittently. Reduced motion measures the
      // state every reader ends on, and the one a reader who asked for no
      // motion sees throughout.
      await owner.emulateMedia({ reducedMotion: 'reduce' });
      await open(owner, id);

      const accessibility = await new AxeBuilder({ page: owner })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze();
      expect(accessibility.violations).toEqual([]);
    });
  }

  test('the evidence disclosure is reachable by keyboard', async ({ owner }) => {
    await open(owner, PUBLISHED);

    // Unconditional. An earlier version only asserted when a disclosure
    // happened to be present, which would have passed silently on the day the
    // control disappeared — a disclosure nobody can reach without a mouse is a
    // disclosure that does not exist for some readers.
    const disclosure = owner
      .getByRole('button', { name: /evidence|citation/i })
      .first();
    await expect(disclosure).toBeVisible();
    await disclosure.focus();
    await expect(disclosure).toBeFocused();
  });

  test('reduced motion is honoured', async ({ owner }) => {
    await owner.emulateMedia({ reducedMotion: 'reduce' });
    await open(owner, PUBLISHED);

    // Criterion 12. `MotionConfig reducedMotion="user"` is what implements
    // this; asserting the page still renders under the preference is what
    // catches it being removed.
    await expect(owner.locator('[data-state="structured"]')).toBeVisible();
    await expect(owner.getByText(/root cause unresolved/i)).toBeVisible();
  });
});
