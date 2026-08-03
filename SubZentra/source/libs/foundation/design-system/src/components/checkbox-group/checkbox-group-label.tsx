/**
 * CheckboxGroup.Label sub-component
 * @module components/checkbox-group
 */
import React from 'react';

import { useTheme } from '../../theme';
import { Checkbox } from '../checkbox';
import { useCheckboxGroupContext } from './checkbox-group.context';
import type { CheckboxGroupLabelProps } from './types';
import { checkboxGroupDefaultTheme } from './types';

/**
 * CheckboxGroup.Label component
 *
 * Optional label for the checkbox group. Can optionally act as a "select all" toggle.
 *
 * @example
 * // Simple label
 * <CheckboxGroup>
 *   <CheckboxGroup.Label>Select options:</CheckboxGroup.Label>
 *   <CheckboxGroup.Item value="a">A</CheckboxGroup.Item>
 * </CheckboxGroup>
 *
 * @example
 * // Select all toggle
 * <CheckboxGroup>
 *   <CheckboxGroup.Label selectAll>Select all</CheckboxGroup.Label>
 *   <CheckboxGroup.Item value="a">A</CheckboxGroup.Item>
 *   <CheckboxGroup.Item value="b">B</CheckboxGroup.Item>
 * </CheckboxGroup>
 */
export const CheckboxGroupLabel: React.FC<CheckboxGroupLabelProps> = ({
  selectAll,
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('checkboxGroup', checkboxGroupDefaultTheme);
  const {
    value: groupValue,
    onValueChange,
    disabled,
    size,
    allItemValues = [],
  } = useCheckboxGroupContext();

  // Calculate select all state
  const allSelected =
    allItemValues.length > 0 && allItemValues.every((v) => groupValue.includes(v));
  const someSelected = allItemValues.some((v) => groupValue.includes(v));
  const isIndeterminate = someSelected && !allSelected;

  const handleSelectAll = (checked: boolean | 'indeterminate') => {
    if (checked === 'indeterminate') return;

    if (checked) {
      // Select all items
      const newValue = [...new Set([...groupValue, ...allItemValues])];
      onValueChange(newValue);
    } else {
      // Deselect all items
      onValueChange(groupValue.filter((v) => !allItemValues.includes(v)));
    }
  };

  // Map size to checkbox size
  const checkboxSize = size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md';

  if (selectAll) {
    return (
      <label
        className={theme.groupLabel?.({ className, size }) ?? className}
        data-ozid={ozid}
        data-slot="label"
      >
        <Checkbox
          checked={isIndeterminate ? 'indeterminate' : allSelected}
          onCheckedChange={handleSelectAll}
          disabled={disabled || allItemValues.length === 0}
          size={checkboxSize}
          indeterminate={isIndeterminate}
          ozid={ozid ? `${ozid}__select-all` : undefined}
        />
        <span className={theme.label?.({ size }) ?? ''}>{children}</span>
      </label>
    );
  }

  return (
    <div
      className={theme.groupLabel?.({ className, size }) ?? className}
      data-ozid={ozid}
      data-slot="label"
    >
      <span className={theme.label?.({ size }) ?? ''}>{children}</span>
    </div>
  );
};

CheckboxGroupLabel.displayName = 'CheckboxGroup.Label';
