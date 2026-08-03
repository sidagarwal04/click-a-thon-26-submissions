/**
 * CheckboxGroup context for sharing selection state with items
 * @module components/checkbox-group
 */
import { createContext, useContext } from 'react';

import type { CheckboxGroupContextValue } from './types';

/**
 * CheckboxGroup context
 *
 * Provides selection state and handlers to CheckboxGroup.Item components.
 * Can also be consumed by external components (MultiSelect, Menu) for custom integrations.
 */
export const CheckboxGroupContext = createContext<CheckboxGroupContextValue | null>(null);

/**
 * Hook to consume CheckboxGroup context
 *
 * @throws Error if used outside of CheckboxGroup.Root
 * @returns The CheckboxGroup context value
 *
 * @example
 * // Inside a custom checkbox item
 * const { value, onValueChange, disabled, size } = useCheckboxGroupContext();
 * const isChecked = value.includes(myItemValue);
 */
export function useCheckboxGroupContext(): CheckboxGroupContextValue {
  const context = useContext(CheckboxGroupContext);
  if (!context) {
    throw new Error(
      'CheckboxGroup compound components must be used within a CheckboxGroup component. ' +
        'Wrap your items with <CheckboxGroup> or <CheckboxGroup.Root>.',
    );
  }
  return context;
}

/**
 * Optional hook that returns null instead of throwing if used outside context
 *
 * Useful for components that can optionally be used inside a CheckboxGroup
 */
export function useOptionalCheckboxGroupContext(): CheckboxGroupContextValue | null {
  return useContext(CheckboxGroupContext);
}
