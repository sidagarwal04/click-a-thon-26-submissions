/**
 * Popover context for sharing state with sub-components
 * @module components/popover
 */
import { createContext, useContext } from 'react';

import type { PopoverContextValue } from './types';

/**
 * Popover context
 */
export const PopoverContext = createContext<PopoverContextValue | null>(null);

/**
 * Hook to consume Popover context
 */
export function usePopoverContext(): PopoverContextValue {
  const context = useContext(PopoverContext);
  if (!context) {
    throw new Error('Popover compound components must be used within a Popover component');
  }
  return context;
}
