/**
 * Accordion context for sharing state with sub-components
 * @module components/accordion
 */
import { createContext, useContext } from 'react';

import type { AccordionContextValue } from './types';

/**
 * Accordion context
 */
export const AccordionContext = createContext<AccordionContextValue | null>(null);

/**
 * Hook to consume Accordion context
 */
export function useAccordionContext(): AccordionContextValue {
  const context = useContext(AccordionContext);
  if (!context) {
    throw new Error('Accordion compound components must be used within an Accordion component');
  }
  return context;
}
