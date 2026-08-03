/**
 * Select component using Base UI
 * @module components/select
 */
import { Select as SelectPrimitive } from '@base-ui/react/select';

import { SelectContent } from './select-content';
import { SelectItem } from './select-item';
import { SelectTrigger } from './select-trigger';
import { SelectProvider } from './select.context';
import type { SelectProps } from './types';

/**
 * Select component
 *
 * An accessible select/dropdown component built on Base UI primitives.
 * Uses compound component pattern with subcomponents.
 *
 * @example
 * <Select defaultValue="option1">
 *   <Select.Trigger placeholder="Select an option" />
 *   <Select.Content>
 *     <Select.Item value="option1">Option 1</Select.Item>
 *     <Select.Item value="option2">Option 2</Select.Item>
 *     <Select.Item value="option3">Option 3</Select.Item>
 *   </Select.Content>
 * </Select>
 *
 * @example
 * // Controlled
 * <Select value={value} onValueChange={setValue}>
 *   <Select.Trigger placeholder="Choose..." />
 *   <Select.Content>
 *     {options.map(opt => (
 *       <Select.Item key={opt.value} value={opt.value}>
 *         {opt.label}
 *       </Select.Item>
 *     ))}
 *   </Select.Content>
 * </Select>
 */
function SelectRoot({
  children,
  ozid,
  size = 'md',
  disabled,
  value,
  defaultValue,
  onValueChange,
  required,
  name,
  open,
  defaultOpen,
  onOpenChange,
}: SelectProps) {
  // Wrap onValueChange to match Base UI's signature
  const handleValueChange = onValueChange
    ? (newValue: string | null) => {
        if (newValue !== null) {
          onValueChange(newValue);
        }
      }
    : undefined;

  return (
    <SelectProvider value={{ size, disabled, ozid }}>
      <SelectPrimitive.Root
        value={value}
        defaultValue={defaultValue}
        onValueChange={handleValueChange}
        required={required}
        name={name}
        open={open}
        defaultOpen={defaultOpen}
        onOpenChange={onOpenChange}
        disabled={disabled}
      >
        {children}
      </SelectPrimitive.Root>
    </SelectProvider>
  );
}

SelectRoot.displayName = 'Select';

/**
 * Select compound component with subcomponents
 */
export const Select = Object.assign(SelectRoot, {
  Trigger: SelectTrigger,
  Content: SelectContent,
  Item: SelectItem,
  /** Re-export Base UI primitives for advanced use cases */
  Value: SelectPrimitive.Value,
  Group: SelectPrimitive.Group,
  GroupLabel: SelectPrimitive.GroupLabel,
  Separator: SelectPrimitive.Separator,
});
