/**
 * Checkbox component type definitions
 * @module components/checkbox/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIDefaultProps,
} from '../../types';

/**
 * Checkbox variant definitions
 */
export const CheckboxVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Checkbox modifier definitions
 * Note: 'checked' is not included here because it has a special type (boolean | 'indeterminate')
 * that differs from the standard boolean modifier type. It's defined manually in CheckboxOwnProps.
 */
export const CheckboxModifiers = ['disabled', 'indeterminate'] as const;

/**
 * Checkbox slot definitions
 */
export const CheckboxSlots = ['indicator'] as const;

/**
 * Checkbox's own props
 */
export interface CheckboxOwnProps
  extends OIComponentOwnProps<
    typeof CheckboxVariants,
    typeof CheckboxModifiers,
    typeof CheckboxSlots
  > {
  /** Checkbox checked state */
  checked?: boolean | 'indeterminate';
  /** Default checked state (uncontrolled) */
  defaultChecked?: boolean;
  /** Change handler */
  onCheckedChange?: (checked: boolean | 'indeterminate') => void;
  /** Required attribute */
  required?: boolean;
  /** Name for form submission */
  name?: string;
  /** Value for form submission */
  value?: string;
  /** ID for label association */
  id?: string;
}

/**
 * Checkbox component props
 */
export type CheckboxProps = OIDefaultProps &
  CheckboxOwnProps &
  // Base UI's Checkbox.Root renders a span carrying role="checkbox", not a
  // button, so the element type here follows what actually reaches the DOM.
  Omit<React.HTMLAttributes<HTMLSpanElement>, keyof CheckboxOwnProps | 'className'>;

/**
 * Checkbox component type
 */
export type CheckboxComponent = React.ForwardRefExoticComponent<
  CheckboxProps & { ref?: React.Ref<HTMLSpanElement> }
>;

/**
 * Default theme configuration for Checkbox
 */
export const checkboxDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'peer shrink-0 rounded border border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-border-focus disabled:cursor-not-allowed data-[state=checked]:bg-primary data-[state=checked]:border-primary data-[state=checked]:text-primary-foreground data-[state=indeterminate]:bg-primary data-[state=indeterminate]:border-primary data-[state=indeterminate]:text-primary-foreground',
    variants: {
      size: {
        sm: 'h-4 w-4',
        md: 'h-5 w-5',
        lg: 'h-6 w-6',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50',
        false: '',
      },
      checked: {
        true: '',
        false: '',
      },
      indeterminate: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    indicator: {
      base: 'flex items-center justify-center text-current',
      variants: {
        size: {
          sm: '',
          md: '',
          lg: '',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
