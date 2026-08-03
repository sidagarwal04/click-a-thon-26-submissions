/**
 * Menu context for sharing state with sub-components
 * @module components/menu
 */
import { createContext, useContext } from 'react';

import type { MenuContextValue } from './types';

/**
 * Menu context
 */
export const MenuContext = createContext<MenuContextValue | null>(null);

/**
 * Hook to consume Menu context
 */
export function useMenuContext(): MenuContextValue {
  const context = useContext(MenuContext);
  if (!context) {
    throw new Error('Menu compound components must be used within a Menu component');
  }
  return context;
}

/**
 * Optional hook that returns null if used outside Menu context
 */
export function useOptionalMenuContext(): MenuContextValue | null {
  return useContext(MenuContext);
}
