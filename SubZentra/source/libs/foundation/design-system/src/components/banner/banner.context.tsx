/**
 * Banner context for ARIA and dismiss handling
 * @module components/banner
 */
import { createContext, useContext } from 'react';

import type { BannerContextValue } from './types';

/**
 * Banner context - provides ARIA IDs and dismiss handler to sub-components
 */
export const BannerContext = createContext<BannerContextValue | null>(null);

/**
 * Hook to consume Banner context
 *
 * @throws Error if used outside of Banner component
 */
export function useBannerContext(): BannerContextValue {
  const context = useContext(BannerContext);
  if (!context) {
    throw new Error('Banner compound components must be used within a Banner component');
  }
  return context;
}
