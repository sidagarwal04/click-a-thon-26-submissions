/**
 * Accordion component
 * @module components/accordion
 */
import React, { useMemo } from 'react';

import { Accordion as AccordionPrimitive } from '@base-ui/react/accordion';

import { useTheme } from '../../theme';
import { AccordionContent } from './accordion-content';
import { AccordionItem } from './accordion-item';
import { AccordionTrigger } from './accordion-trigger';
import { AccordionContext } from './accordion.context';
import type { AccordionComponent, AccordionContextValue, AccordionProps } from './types';
import { accordionDefaultTheme } from './types';

/**
 * Accordion component
 *
 * A vertically stacked set of interactive headings that reveal content.
 *
 * @example
 * <Accordion>
 *   <Accordion.Item value="item-1">
 *     <Accordion.Trigger>Section 1</Accordion.Trigger>
 *     <Accordion.Content>Content for section 1</Accordion.Content>
 *   </Accordion.Item>
 *   <Accordion.Item value="item-2">
 *     <Accordion.Trigger>Section 2</Accordion.Trigger>
 *     <Accordion.Content>Content for section 2</Accordion.Content>
 *   </Accordion.Item>
 * </Accordion>
 */
const AccordionRoot = React.forwardRef<HTMLDivElement, AccordionProps>(function Accordion(
  {
    ozid,
    variant = 'default',
    multiple = false,
    value,
    defaultValue,
    onValueChange,
    disabled,
    children,
    className,
    ...rest
  },
  ref,
) {
  const theme = useTheme('accordion', accordionDefaultTheme);

  // Context value for sub-components
  const contextValue: AccordionContextValue = useMemo(
    () => ({
      variant,
      disabled,
    }),
    [variant, disabled],
  );

  return (
    <AccordionContext.Provider value={contextValue}>
      {/* rest first: caller-supplied lang, aria and data attributes reach the
          root, but never at the cost of the props managed here. */}
      <AccordionPrimitive.Root
        {...rest}
        ref={ref}
        value={value}
        defaultValue={defaultValue}
        onValueChange={onValueChange}
        className={theme.root?.({ className, variant, disabled }) ?? className}
        data-ozid={ozid}
      >
        {children}
      </AccordionPrimitive.Root>
    </AccordionContext.Provider>
  );
}) as AccordionComponent;

// Attach sub-components
AccordionRoot.displayName = 'Accordion';
AccordionRoot.Item = AccordionItem;
AccordionRoot.Trigger = AccordionTrigger;
AccordionRoot.Content = AccordionContent;

export const Accordion = AccordionRoot;
