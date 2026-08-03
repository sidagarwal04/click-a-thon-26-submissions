/**
 * Accordion.Content sub-component
 * @module components/accordion
 */
import React from 'react';

import { Accordion as AccordionPrimitive } from '@base-ui/react/accordion';

import { useTheme } from '../../theme';
import type { AccordionContentProps } from './types';
import { accordionDefaultTheme } from './types';

/**
 * Accordion.Content component
 *
 * Container for the accordion item content.
 */
export const AccordionContent: React.FC<AccordionContentProps> = ({
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('accordion', accordionDefaultTheme);

  return (
    <AccordionPrimitive.Panel
      className={theme.content?.({ className }) ?? className}
      data-ozid={ozid}
      data-slot="content"
    >
      <div className={theme.contentInner?.({}) ?? ''}>{children}</div>
    </AccordionPrimitive.Panel>
  );
};

AccordionContent.displayName = 'Accordion.Content';
