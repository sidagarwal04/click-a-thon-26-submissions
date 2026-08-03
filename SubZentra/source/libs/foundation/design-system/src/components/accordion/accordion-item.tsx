/**
 * Accordion.Item sub-component
 * @module components/accordion
 */
import React from 'react';

import { Accordion as AccordionPrimitive } from '@base-ui/react/accordion';

import { useTheme } from '../../theme';
import { useAccordionContext } from './accordion.context';
import type { AccordionItemProps } from './types';
import { accordionDefaultTheme } from './types';

/**
 * Accordion.Item component
 *
 * Container for a single accordion item.
 */
export const AccordionItem: React.FC<AccordionItemProps> = ({
  value,
  disabled,
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('accordion', accordionDefaultTheme);
  const { variant, disabled: groupDisabled } = useAccordionContext();
  const isDisabled = disabled || groupDisabled;

  return (
    <AccordionPrimitive.Item
      value={value}
      disabled={isDisabled}
      className={theme.item?.({ className, variant, disabled: isDisabled }) ?? className}
      data-ozid={ozid}
      data-slot="item"
    >
      {children}
    </AccordionPrimitive.Item>
  );
};

AccordionItem.displayName = 'Accordion.Item';
