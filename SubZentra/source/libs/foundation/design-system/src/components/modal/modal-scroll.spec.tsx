/// <reference types="vitest/globals" />
import { render, screen } from '@testing-library/react';

import { Modal } from './index';

/**
 * The chain that makes a long modal scroll instead of running off the screen.
 *
 * Asserted as classes rather than as behaviour because jsdom does no layout —
 * there is no scroll height to measure. That makes this a structural guard, and
 * it is worth having: this broke twice, silently, and the symptom only appears
 * with enough content to overflow a real viewport.
 *
 * Each link matters on its own:
 *   popup      capped height, a flex column, clipping what outgrows it
 *   inner      `flex-1 min-h-0` — `min-h-0` is what lets it shrink below its
 *              content, since its own overflow is visible
 *   header     `shrink-0`, so the body yields space rather than the title
 *   body       `flex-1 overflow-auto` — the scroll container itself
 */
describe('Modal scrolling', () => {
  const renderModal = () =>
    render(
      <Modal open size="960">
        <Modal.Content>
          <Modal.Header>
            <Modal.Title>Long table</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <p>Rows</p>
          </Modal.Body>
          <Modal.Footer>
            <button type="button">Close</button>
          </Modal.Footer>
        </Modal.Content>
      </Modal>,
    );

  it('caps the popup at the viewport, as a clipping flex column', () => {
    renderModal();
    const popup = document.querySelector('[data-slot="content"]');

    expect(popup?.className).toContain('flex');
    expect(popup?.className).toContain('flex-col');
    expect(popup?.className).toContain('overflow-hidden');
    expect(popup?.className).toContain('max-h-[calc(100vh-4rem)]');
  });

  it('lets the inner column shrink below its content', () => {
    renderModal();
    const inner = document.querySelector('[data-slot="content"] > div');

    // `h-full` here would resolve against an indeterminate height and collapse
    // to auto, which is exactly how the overflow bug came back.
    expect(inner?.className).toContain('min-h-0');
    expect(inner?.className).toContain('flex-1');
    expect(inner?.className).not.toContain('h-full');
  });

  it('makes the body the scroll container and the chrome hold its size', () => {
    renderModal();
    const body = document.querySelector('[data-slot="body"]');

    expect(body?.className).toContain('overflow-auto');
    expect(body?.className).toContain('flex-1');
    expect(screen.getByText('Long table').closest('[class*="shrink-0"]')).toBeTruthy();
  });
});
