/**
 * Modal context for sharing state with sub-components
 * @module components/modal
 */
import { createContext, useContext } from 'react';

import type { ModalContextValue } from './types';

/**
 * Modal context - provides size, fill settings, and ARIA IDs to sub-components
 */
export const ModalContext = createContext<ModalContextValue | null>(null);

/**
 * Hook to consume Modal context
 *
 * @throws Error if used outside of Modal component
 */
export function useModalContext(): ModalContextValue {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('Modal compound components must be used within a Modal component');
  }
  return context;
}
