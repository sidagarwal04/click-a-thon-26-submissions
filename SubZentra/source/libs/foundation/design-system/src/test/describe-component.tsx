/**
 * Component test harness
 * @module test/describe-component
 */

import React from 'react';

import { render } from '@testing-library/react';
import camelCase from 'lodash-es/camelCase';

import { ThemeProvider } from '../theme';
import type { OIComponentModifiers, OIComponentVariants } from '../types';
import { slotOzid } from '../utils/ozid';
import { randomString } from './random';
import { resetTestingComponentState, setTestingComponentState } from './test-state';

export interface DescribeComponentOptions {
  /** The modifiers component does support */
  modifiers?: OIComponentModifiers;
  /** The component name */
  name: string;
  /** The default HTMLElement the element is rendered by default */
  rootInstanceOf: unknown;
  /** The root slot supports aria attributes, default: true */
  rootSupportsAriaAttributes?: boolean;
  /** The variants component does support */
  variants?: OIComponentVariants;
  /**
   * If true, component should support polymorphism
   * @default true
   */
  shouldSupportPolymorphism?: boolean;
  /**
   * If true, component will be tested if it supports forwarding ref to the root element.
   * @default true
   */
  shouldSupportForwardRef?: boolean;
  /**
   * For compound components whose root renders no DOM element.
   *
   * Base UI roots such as Dialog.Root are context providers: they emit no host
   * node, so cloning the root with className/ozid/lang/aria-* has nothing to
   * land on and every root-element assertion fails by construction. Such a
   * component nominates the element that *is* its DOM root — usually its
   * Content slot — and the contract is applied there instead.
   *
   * This redirects the contract; it never relaxes it. The component still has
   * to accept every one of those props somewhere.
   */
  renderRoot?: (rootProps: Record<string, unknown>) => React.ReactElement;
  /**
   * Theme slot the DOM root is styled from, when it is not `root`.
   *
   * Goes with `renderRoot`: a compound component's real root element is usually
   * a named slot (Modal's is `popup`), so its variant and modifier classes are
   * configured under that slot rather than under `root`.
   *
   * @default 'root'
   */
  rootSlot?: string;
}

/**
 * Splits harness props into the ones the DOM root must carry and the ones that
 * are the component's own API.
 *
 * A compound component takes its variants and modifiers on the outer root — the
 * context provider — while className, ozid, ref and plain HTML attributes have
 * to land on the element that actually reaches the document. `renderRoot`
 * implementations use this to send each prop to the right place.
 */
export const splitRootProps = (
  props: Record<string, unknown>,
): { domProps: Record<string, unknown>; ownProps: Record<string, unknown> } => {
  const domProps: Record<string, unknown> = {};
  const ownProps: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(props)) {
    const belongsOnDomRoot =
      key === 'className' ||
      key === 'ozid' ||
      key === 'ref' ||
      key === 'lang' ||
      key.startsWith('aria-') ||
      key.startsWith('data-');
    (belongsOnDomRoot ? domProps : ownProps)[key] = value;
  }
  return { domProps, ownProps };
};

/**
 * Builds a ThemeProvider config placing `slotConfig` at the right depth.
 *
 * `root` sits at the top of a component's theme config; every other slot lives
 * under `slots`. Writing a named slot flat, as this harness used to, produces a
 * config the resolver silently ignores — the component keeps its defaults and
 * the assertion fails with no indication why.
 */
const themeConfigFor = (
  themeKey: string,
  slot: string,
  slotConfig: Record<string, unknown>,
): Record<string, unknown> => ({
  components: {
    [themeKey]: slot === 'root' ? { root: slotConfig } : { slots: { [slot]: slotConfig } },
  },
});

/**
 * Produces the element to render with the contract's props applied to whatever
 * the component's real DOM root is.
 */
type RenderWithRootProps = (rootProps: Record<string, unknown>) => React.ReactElement;

const rootPropsRenderer = (
  element: React.ReactElement,
  renderRoot: DescribeComponentOptions['renderRoot'],
): RenderWithRootProps =>
  renderRoot ?? ((rootProps) => React.cloneElement(element, rootProps));

/**
 * Tests className property support
 */
function testSupportsClassName(renderWith: RenderWithRootProps) {
  it('supports className property', () => {
    const ozid = randomString();
    const className = randomString('test-class-name');
    const { getByTestId } = render(renderWith({ className, ozid }));
    expect(getByTestId(ozid)).toHaveClass(className);
  });
}

/**
 * Tests ozid property support
 */
function testSupportsOzid(renderWith: RenderWithRootProps) {
  it('supports ozid property', () => {
    const ozid = randomString();
    const { getByTestId } = render(renderWith({ ozid }));
    expect(getByTestId(ozid)).toHaveAttribute('data-ozid', ozid);
    expect(getByTestId(ozid)).toBeInTheDocument();
  });
}

/**
 * Tests ref forwarding support
 */
function testSupportsForwardRef(
  renderWith: RenderWithRootProps,
  rootInstanceOf: DescribeComponentOptions['rootInstanceOf'],
) {
  it('supports forwarding ref to root element', () => {
    const ref = React.createRef();
    const ozid = randomString();
    const { getByTestId } = render(renderWith({ ozid, ref }));
    expect(ref.current).toBeInstanceOf(rootInstanceOf);
    expect(getByTestId(ozid)).toEqual(ref.current);
  });
}

/**
 * Tests common HTML attributes support
 */
function testSupportsCommonHTMLAttributes(
  renderWith: RenderWithRootProps,
  { rootSupportsAriaAttributes }: Pick<DescribeComponentOptions, 'rootSupportsAriaAttributes'>,
) {
  it('should support passing lang attribute to root element', () => {
    const ozid = randomString();
    const lang = 'en';
    const { getByTestId } = render(renderWith({ ozid, lang }));
    expect(getByTestId(ozid)).toHaveAttribute('lang', lang);
  });

  if (rootSupportsAriaAttributes) {
    it('should support passing aria attribute to root element', () => {
      const ozid = randomString();
      const ariaAttrName = 'aria-labelledby';
      const ariaAttrValue = randomString('aria-labelledby');
      const { getByTestId } = render(renderWith({ [ariaAttrName]: ariaAttrValue, ozid }));
      expect(getByTestId(ozid)).toHaveAttribute(ariaAttrName, ariaAttrValue);
    });
  }

  it('should support passing data-* attributes to root element', () => {
    const ozid = randomString();
    const dataAttrName = randomString('data');
    const dataAttrValue = randomString();
    const { getByTestId } = render(renderWith({ [dataAttrName]: dataAttrValue, ozid }));
    expect(getByTestId(ozid)).toHaveAttribute(dataAttrName, dataAttrValue);
  });
}

/**
 * Tests polymorphism support
 */
function testSupportsComponentProp(renderWith: RenderWithRootProps) {
  it('should render the root element with provided component', () => {
    const ozid = randomString();
    const { getByTestId } = render(renderWith({ component: 'i', ozid }));
    expect(getByTestId(ozid).nodeName).toBe('I');
  });

  it('should render the root element with provided React component', () => {
    const ozid = randomString();
    const testContent = randomString();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Component = React.forwardRef<HTMLDivElement, any>((props, ref) => (
      <div ref={ref} {...props}>
        {testContent}
      </div>
    ));
    Component.displayName = 'TestComponent';
    const { getByTestId } = render(renderWith({ component: Component, ozid }));
    expect(getByTestId(ozid)).toHaveTextContent(testContent);
  });
}

/**
 * Tests modifiers support
 */
export function testModifiers(
  themeKey: string,
  element: React.ReactElement,
  modifiers: readonly string[],
  slot = 'root',
  {
    allowMultiple = false,
    renderRoot,
    themeSlot,
  }: { allowMultiple?: boolean; renderRoot?: RenderWithRootProps; themeSlot?: string } = {},
) {
  // A component may legitimately declare no modifiers. Opening the describe
  // block anyway produces "No test found in suite modifiers", which fails the
  // run for components that have done nothing wrong.
  if (modifiers.length === 0) {
    return;
  }

  const renderWith = renderRoot ?? ((props) => React.cloneElement(element, props));
  // The theme slot and the queried element are not always the same: a compound
  // component's DOM root is styled from a named slot (Modal's is `popup`) while
  // still carrying the plain ozid.
  const styledSlot = themeSlot ?? slot;
  describe('modifiers', () => {
    for (const modifier of modifiers) {
      const trueClassName = randomString('modifier-true');
      const falseClassName = randomString('modifier-false');
      const themeConfig = themeConfigFor(themeKey, styledSlot, {
        modifiers: {
          [modifier]: { true: trueClassName, false: falseClassName },
        },
      });
      const ozid = randomString(modifier);

      it(`should support modifier: ${modifier}=true`, () => {
        const { getByTestId, getAllByTestId } = render(
          <ThemeProvider theme={themeConfig}>
            {renderWith({ ozid, [modifier]: true })}
          </ThemeProvider>,
        );
        if (allowMultiple) {
          const renderedElements = getAllByTestId(
            slot === 'root' ? ozid : slotOzid(ozid, slot) ?? '',
          );
          for (const renderedElement of renderedElements) {
            expect(renderedElement).toHaveClass(trueClassName);
            expect(renderedElement).not.toHaveClass(falseClassName);
          }
        } else {
          const renderedElement = getByTestId(slot === 'root' ? ozid : slotOzid(ozid, slot) ?? '');
          expect(renderedElement).toHaveClass(trueClassName);
          expect(renderedElement).not.toHaveClass(falseClassName);
        }
      });

      it(`should support modifier: ${modifier}=false`, () => {
        const { getByTestId, getAllByTestId } = render(
          <ThemeProvider theme={themeConfig}>
            {renderWith({ ozid, [modifier]: false })}
          </ThemeProvider>,
        );
        if (allowMultiple) {
          const renderedElements = getAllByTestId(
            slot === 'root' ? ozid : slotOzid(ozid, slot) ?? '',
          );
          for (const renderedElement of renderedElements) {
            expect(renderedElement).toHaveClass(falseClassName);
            expect(renderedElement).not.toHaveClass(trueClassName);
          }
        } else {
          const renderedElement = getByTestId(slot === 'root' ? ozid : slotOzid(ozid, slot) ?? '');
          expect(renderedElement).toHaveClass(falseClassName);
          expect(renderedElement).not.toHaveClass(trueClassName);
        }
      });
    }
  });
}

/**
 * Ensures variants structure is valid
 */
export function ensureVariantsStructure(variants: { [variant: string]: readonly string[] }) {
  if (variants == null && typeof variants !== 'object') {
    throw new Error('variants is not an object');
  }
  for (const [key, value] of Object.entries(variants)) {
    if (!Array.isArray(value) || value.some((v) => typeof v !== 'string')) {
      throw new Error(`variants.${key} is not an array of strings`);
    }
  }
}

/**
 * Tests variants support
 */
export function testVariants(
  themeKey: string,
  element: React.ReactElement,
  variants: NonNullable<DescribeComponentOptions['variants']>,
  slot = 'root',
  {
    allowMultiple = false,
    renderRoot,
    themeSlot,
  }: { allowMultiple?: boolean; renderRoot?: RenderWithRootProps; themeSlot?: string } = {},
) {
  const renderWith = renderRoot ?? ((props) => React.cloneElement(element, props));
  const styledSlot = themeSlot ?? slot;
  for (const [variant, values] of Object.entries(variants)) {
    describe(`variant: ${variant}`, () => {
      const valuesClassNames = values.reduce((obj, value) => {
        obj[value] = randomString(`variant-cn-${variant}-${value}`);
        return obj;
      }, {} as Record<string, string>);
      const themeConfig = themeConfigFor(themeKey, styledSlot, {
        variants: { [variant]: valuesClassNames },
      });

      for (const value of values) {
        const ozid = randomString(`test-variant-${variant}`);
        it(`should support value: ${value}`, () => {
          const { getByTestId, getAllByTestId } = render(
            <ThemeProvider theme={themeConfig}>
              {renderWith({ ozid, [variant]: value })}
            </ThemeProvider>,
          );
          if (allowMultiple) {
            const renderedElements = getAllByTestId(
              slot === 'root' ? ozid : slotOzid(ozid, slot) ?? '',
            );
            for (const renderedElement of renderedElements) {
              for (const otherValue of values) {
                if (otherValue === value) {
                  expect(renderedElement).toHaveClass(valuesClassNames[otherValue]);
                } else {
                  expect(renderedElement).not.toHaveClass(valuesClassNames[otherValue]);
                }
              }
            }
          } else {
            const renderedElement = getByTestId(
              slot === 'root' ? ozid : slotOzid(ozid, slot) ?? '',
            );
            for (const otherValue of values) {
              if (otherValue === value) {
                expect(renderedElement).toHaveClass(valuesClassNames[otherValue]);
              } else {
                expect(renderedElement).not.toHaveClass(valuesClassNames[otherValue]);
              }
            }
          }
        });
      }
    });
  }
}

/**
 * Main test harness for OpenZentra Design System components
 *
 * @example
 * describeComponent(
 *   <Button>Click me</Button>,
 *   {
 *     name: 'Button',
 *     rootInstanceOf: window.HTMLButtonElement,
 *     variants: ButtonVariants,
 *     modifiers: ButtonModifiers,
 *   },
 *   () => {
 *     // Custom tests
 *   }
 * );
 */
export function describeComponent(
  minimumElement: React.ReactElement,
  {
    name,
    variants,
    modifiers,
    rootInstanceOf,
    rootSupportsAriaAttributes = true,
    shouldSupportPolymorphism = true,
    shouldSupportForwardRef = true,
    renderRoot,
    rootSlot = 'root',
  }: DescribeComponentOptions,
  customTests?: () => void,
): void {
  const componentThemeKey = camelCase(name);
  setTestingComponentState({ name, themeKey: componentThemeKey });

  if (!name) {
    throw new Error('You need to provide the "name"');
  }

  const renderWith = rootPropsRenderer(minimumElement, renderRoot);

  describe(`OI component: <${name} />`, () => {
    describe('common:', () => {
      testSupportsClassName(renderWith);
      testSupportsOzid(renderWith);
      if (shouldSupportForwardRef) {
        testSupportsForwardRef(renderWith, rootInstanceOf);
      }
      testSupportsCommonHTMLAttributes(renderWith, { rootSupportsAriaAttributes });
      if (shouldSupportPolymorphism) {
        testSupportsComponentProp(renderWith);
      }
    });

    if (modifiers) {
      if (!Array.isArray(modifiers) || modifiers.some((v) => typeof v !== 'string')) {
        throw new Error('modifiers is not an array of strings');
      }
      testModifiers(componentThemeKey, minimumElement, modifiers, 'root', {
        renderRoot: renderWith,
        themeSlot: rootSlot,
      });
    }

    if (variants) {
      ensureVariantsStructure(variants);
      testVariants(componentThemeKey, minimumElement, variants, 'root', {
        renderRoot: renderWith,
        themeSlot: rootSlot,
      });
    }

    customTests?.();
    resetTestingComponentState();
  });
}
