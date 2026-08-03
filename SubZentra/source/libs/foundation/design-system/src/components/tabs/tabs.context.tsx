/**
 * Tabs context for sharing state with sub-components
 * @module components/tabs
 */
import { createContext, useContext } from 'react';

import type { TabsContextValue } from './types';

/**
 * Tabs context
 */
export const TabsContext = createContext<TabsContextValue | null>(null);

/**
 * Hook to consume Tabs context
 */
export function useTabsContext(): TabsContextValue {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('Tabs compound components must be used within a Tabs component');
  }
  return context;
}
