/**
 * CheckboxGroup.Item sub-component
 * @module components/checkbox-group
 */
import React, { useEffect } from 'react';

import { useTheme } from '../../theme';
import { Checkbox } from '../checkbox';
import { useCheckboxGroupContext } from './checkbox-group.context';
import type { CheckboxGroupItemProps } from './types';
import { checkboxGroupDefaultTheme } from './types';

/**
 * CheckboxGroup.Item component
 *
 * A checkbox item that integrates with CheckboxGroup selection state.
 * Uses the foundation Checkbox component internally.
 *
 * @example
 * <CheckboxGroup value={selected} onValueChange={setSelected}>
 *   <CheckboxGroup.Item value="option1">Option 1</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="option2">Option 2</CheckboxGroup.Item>
 * </CheckboxGroup>
 */
export const CheckboxGroupItem: React.FC<CheckboxGroupItemProps> = ({
  value: itemValue,
  disabled: itemDisabled,
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('checkboxGroup', checkboxGroupDefaultTheme);
  const {
    value: groupValue,
    onValueChange,
    disabled: groupDisabled,
    size,
    registerItem,
    unregisterItem,
  } = useCheckboxGroupContext();

  const isDisabled = itemDisabled || groupDisabled;
  const isChecked = groupValue.includes(itemValue);

  // Register/unregister item for select-all functionality
  useEffect(() => {
    registerItem?.(itemValue);
    return () => unregisterItem?.(itemValue);
  }, [itemValue, registerItem, unregisterItem]);

  const handleCheckedChange = (checked: boolean | 'indeterminate') => {
    if (checked === 'indeterminate') return;

    if (checked) {
      // Add to selection
      onValueChange([...groupValue, itemValue]);
    } else {
      // Remove from selection
      onValueChange(groupValue.filter((v) => v !== itemValue));
    }
  };

  // Map size to checkbox size
  const checkboxSize = size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md';

  return (
    <label
      className={theme.item?.({ className, size, disabled: isDisabled }) ?? className}
      data-ozid={ozid}
      data-slot="item"
      data-checked={isChecked || undefined}
      data-disabled={isDisabled || undefined}
    >
      <Checkbox
        checked={isChecked}
        onCheckedChange={handleCheckedChange}
        disabled={isDisabled}
        size={checkboxSize}
        ozid={ozid ? `${ozid}__checkbox` : undefined}
      />
      {children && <span className={theme.label?.({ size }) ?? ''}>{children}</span>}
    </label>
  );
};

CheckboxGroupItem.displayName = 'CheckboxGroup.Item';
