/**
 * CheckboxGroup component
 * @module components/checkbox-group
 *
 * A standalone primitive for managing multi-selection state.
 * Designed to be reused by MultiSelect and Menu components.
 */
import React, { useCallback, useMemo, useState } from 'react';

import { useTheme } from '../../theme';
import { CheckboxGroupItem } from './checkbox-group-item';
import { CheckboxGroupLabel } from './checkbox-group-label';
import { CheckboxGroupContext } from './checkbox-group.context';
import type {
  CheckboxGroupComponent,
  CheckboxGroupContextValue,
  CheckboxGroupProps,
} from './types';
import { checkboxGroupDefaultTheme } from './types';

/**
 * CheckboxGroup component
 *
 * A compound component for managing multiple checkbox selections.
 * Provides context to child items for state management.
 *
 * @example
 * // Controlled
 * const [selected, setSelected] = useState<string[]>(['a']);
 * <CheckboxGroup value={selected} onValueChange={setSelected}>
 *   <CheckboxGroup.Item value="a">Option A</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="b">Option B</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="c">Option C</CheckboxGroup.Item>
 * </CheckboxGroup>
 *
 * @example
 * // Uncontrolled with default value
 * <CheckboxGroup defaultValue={['a']}>
 *   <CheckboxGroup.Item value="a">Option A</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="b">Option B</CheckboxGroup.Item>
 * </CheckboxGroup>
 *
 * @example
 * // With select all label
 * <CheckboxGroup value={selected} onValueChange={setSelected}>
 *   <CheckboxGroup.Label selectAll>Select all</CheckboxGroup.Label>
 *   <CheckboxGroup.Item value="a">Option A</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="b">Option B</CheckboxGroup.Item>
 * </CheckboxGroup>
 *
 * @example
 * // Horizontal layout
 * <CheckboxGroup orientation="horizontal">
 *   <CheckboxGroup.Item value="a">A</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="b">B</CheckboxGroup.Item>
 * </CheckboxGroup>
 */
const CheckboxGroupRoot = React.forwardRef<HTMLDivElement, CheckboxGroupProps>(
  function CheckboxGroup(
    {
      ozid,
      orientation = 'vertical',
      size = 'md',
      value: controlledValue,
      defaultValue = [],
      onValueChange: controlledOnValueChange,
      disabled,
      label,
      children,
      className,
      ...rest
    },
    ref,
  ) {
    const theme = useTheme('checkboxGroup', checkboxGroupDefaultTheme);

    // Internal state for uncontrolled mode
    const [internalValue, setInternalValue] = useState<string[]>(defaultValue);

    // Track all registered item values for select-all functionality
    const [allItemValues, setAllItemValues] = useState<string[]>([]);

    // Determine if controlled or uncontrolled
    const isControlled = controlledValue !== undefined;
    const value = isControlled ? controlledValue : internalValue;

    const onValueChange = useCallback(
      (newValue: string[]) => {
        if (!isControlled) {
          setInternalValue(newValue);
        }
        controlledOnValueChange?.(newValue);
      },
      [isControlled, controlledOnValueChange],
    );

    // Register/unregister items for select-all functionality
    const registerItem = useCallback((itemValue: string) => {
      setAllItemValues((prev) => {
        if (prev.includes(itemValue)) return prev;
        return [...prev, itemValue];
      });
    }, []);

    const unregisterItem = useCallback((itemValue: string) => {
      setAllItemValues((prev) => prev.filter((v) => v !== itemValue));
    }, []);

    // Context value
    const contextValue: CheckboxGroupContextValue = useMemo(
      () => ({
        value,
        onValueChange,
        disabled,
        size,
        orientation,
        registerItem,
        unregisterItem,
        allItemValues,
      }),
      [
        value,
        onValueChange,
        disabled,
        size,
        orientation,
        registerItem,
        unregisterItem,
        allItemValues,
      ],
    );

    return (
      <CheckboxGroupContext.Provider value={contextValue}>
        {/* rest first: caller-supplied lang, aria and data attributes reach the
          root, but never at the cost of the props managed here. */}
        <div
          {...rest}
          ref={ref}
          role="group"
          aria-label={rest['aria-label'] ?? label}
          className={theme.root?.({ className, orientation, size, disabled }) ?? className}
          data-ozid={ozid}
          data-orientation={orientation}
          data-disabled={disabled || undefined}
        >
          {children}
        </div>
      </CheckboxGroupContext.Provider>
    );
  },
) as CheckboxGroupComponent;

// Attach sub-components
CheckboxGroupRoot.displayName = 'CheckboxGroup';
CheckboxGroupRoot.Item = CheckboxGroupItem;
CheckboxGroupRoot.Label = CheckboxGroupLabel;

export const CheckboxGroup = CheckboxGroupRoot;
