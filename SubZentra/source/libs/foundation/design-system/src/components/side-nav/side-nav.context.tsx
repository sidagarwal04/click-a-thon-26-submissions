/**
 * SideNav context for sharing rail state with its items
 * @module components/side-nav
 */
import { createContext, useContext } from 'react';

import type { SideNavVariants } from './types';

export interface SideNavContextValue {
  readonly width: (typeof SideNavVariants.width)[number];
}

/**
 * Defaults to the expanded rail so an item rendered on its own — in a test or
 * a story — still behaves.
 */
export const SideNavContext = createContext<SideNavContextValue>({ width: 'default' });

export function useSideNavContext(): SideNavContextValue {
  return useContext(SideNavContext);
}
