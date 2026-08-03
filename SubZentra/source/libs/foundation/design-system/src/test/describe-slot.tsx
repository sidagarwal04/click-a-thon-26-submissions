/**
 * Slot test utilities
 * @module test/describe-slot
 */

import React from 'react';

import { render } from '@testing-library/react';

import type { OIComponentModifiers, OIComponentSlot, OIComponentVariants } from '../types';
import { slotOzid } from '../utils/ozid';
import { normalizeSlot } from '../utils/slot-helpers';
import { ensureVariantsStructure, testModifiers, testVariants } from './describe-component';
import { randomString } from './random';
import { getTestingComponentState } from './test-state';

export interface DescribeSlotOptions {
  /** The modifiers component does support */
  modifiers: OIComponentModifiers;
  /** The component name */
  name: OIComponentSlot;
  /** The variants component does support */
  variants: OIComponentVariants;
  /** If true, it allows multiple slots to be rendered at the same time with the same name */
  allowMultiple?: boolean;
}

function testCommonSlot(
  element: React.ReactElement,
  slot: string,
  { allowMultiple = false }: { allowMultiple?: boolean } = {},
) {
  it('supports children prop', () => {
    const ozid = randomString();
    const childrenContent = randomString();
    const { getAllByTestId, getByTestId } = render(
      React.cloneElement(element, {
        ozid,
        [slot]: { children: childrenContent },
      }),
    );
    if (allowMultiple) {
      const renderedElements = getAllByTestId(slotOzid(ozid, slot) ?? '');
      for (const renderedElement of renderedElements) {
        expect(renderedElement).toHaveTextContent(childrenContent);
      }
    } else {
      const renderedElement = getByTestId(slotOzid(ozid, slot) ?? '');
      expect(renderedElement).toHaveTextContent(childrenContent);
    }
  });

  it('supports component prop', () => {
    const ozid = randomString();
    const { getAllByTestId, getByTestId } = render(
      React.cloneElement(element, {
        ozid,
        [slot]: { children: 'Test slot', component: 'span' },
      }),
    );
    if (allowMultiple) {
      const renderedElements = getAllByTestId(slotOzid(ozid, slot) ?? '');
      for (const renderedElement of renderedElements) {
        expect(renderedElement).toBeInstanceOf(HTMLSpanElement);
      }
    } else {
      const renderedElement = getByTestId(slotOzid(ozid, slot) ?? '');
      expect(renderedElement).toBeInstanceOf(HTMLSpanElement);
    }
  });

  it('supports component prop with custom component', () => {
    const ozid = randomString();
    const testContent = randomString();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Component = (props: any) => <div {...props}>{testContent}</div>;
    const { getAllByTestId, getByTestId } = render(
      React.cloneElement(element, {
        ozid,
        [slot]: { component: Component },
      }),
    );
    if (allowMultiple) {
      const renderedElements = getAllByTestId(slotOzid(ozid, slot) ?? '');
      for (const renderedElement of renderedElements) {
        expect(renderedElement).toHaveTextContent(testContent);
      }
    } else {
      const renderedElement = getByTestId(slotOzid(ozid, slot) ?? '');
      expect(renderedElement).toHaveTextContent(testContent);
    }
  });
}

/**
 * Tests a slot of a component
 * Can only be called inside describeComponent custom tests
 *
 * @example
 * describeComponent(
 *   <Button>Click</Button>,
 *   { name: 'Button', ... },
 *   () => {
 *     describeSlot(<Button>Test</Button>, {
 *       name: 'startIcon',
 *       modifiers: ButtonModifiers,
 *       variants: ButtonVariants,
 *     });
 *   }
 * );
 */
export function describeSlot(
  minimumElement: React.ReactElement,
  { name, variants, modifiers, allowMultiple }: DescribeSlotOptions,
): void {
  const componentThemeKey = getTestingComponentState().themeKey;
  if (!name) {
    throw new Error('You need to provide the "name"');
  }

  const slot = normalizeSlot(name);
  describe(`slot: ${slot.name}`, () => {
    if (slot.allowOverride) {
      testCommonSlot(minimumElement, slot.name, { allowMultiple });
    }

    if (modifiers) {
      if (!Array.isArray(modifiers) || modifiers.some((v) => typeof v !== 'string')) {
        throw new Error('modifiers is not an array of strings');
      }
      testModifiers(
        componentThemeKey,
        // Components might choose to not render the slot if slot props are not provided
        React.cloneElement(minimumElement, { [slot.name]: { children: <span>Test slot</span> } }),
        modifiers,
        slot.name,
        { allowMultiple },
      );
    }

    if (variants) {
      ensureVariantsStructure(variants);
      testVariants(
        componentThemeKey,
        // Components might choose to not render the slot if slot props are not provided
        React.cloneElement(minimumElement, { [slot.name]: { children: <span>Test slot</span> } }),
        variants,
        slot.name,
        { allowMultiple },
      );
    }
  });
}
