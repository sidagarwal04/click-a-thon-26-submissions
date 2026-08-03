/**
 * Drawer context for sharing state with sub-components
 * @module components/drawer
 */
import { createContext, useContext } from 'react';

import type { DrawerContextValue } from './types';

/**
 * Drawer context - provides direction, size, and ARIA IDs to sub-components
 */
export const DrawerContext = createContext<DrawerContextValue | null>(null);

/**
 * Hook to consume Drawer context
 *
 * @throws Error if used outside of Drawer component
 */
export function useDrawerContext(): DrawerContextValue {
  const context = useContext(DrawerContext);
  if (!context) {
    throw new Error('Drawer compound components must be used within a Drawer component');
  }
  return context;
}
