/**
 * CheckboxGroup component exports
 * @module components/checkbox-group
 *
 * CheckboxGroup is a standalone primitive for managing multi-selection state.
 * It is designed to be reused by MultiSelect and Menu components.
 */

export { CheckboxGroup } from './checkbox-group';
export { CheckboxGroupItem } from './checkbox-group-item';
export { CheckboxGroupLabel } from './checkbox-group-label';
export {
  CheckboxGroupContext,
  useCheckboxGroupContext,
  useOptionalCheckboxGroupContext,
} from './checkbox-group.context';
export type {
  CheckboxGroupProps,
  CheckboxGroupComponent,
  CheckboxGroupOwnProps,
  CheckboxGroupItemProps,
  CheckboxGroupItemOwnProps,
  CheckboxGroupLabelProps,
  CheckboxGroupContextValue,
} from './types';
export {
  CheckboxGroupVariants,
  CheckboxGroupModifiers,
  CheckboxGroupSlots,
  checkboxGroupDefaultTheme,
} from './types';
