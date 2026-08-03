/**
 * RadioGroup component type definitions
 * @module components/radio-group/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentRef,
  OIDefaultProps,
} from '../../types';

/**
 * RadioGroup variant definitions
 */
export const RadioGroupVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * RadioGroup modifier definitions
 */
export const RadioGroupModifiers = ['disabled'] as const;

/**
 * RadioGroup slot definitions
 */
export const RadioGroupSlots = [] as const;

/**
 * RadioGroup's own props
 */
export interface RadioGroupOwnProps
  extends OIComponentOwnProps<
    typeof RadioGroupVariants,
    typeof RadioGroupModifiers,
    typeof RadioGroupSlots
  > {
  /** Current value */
  value?: string;
  /** Default value (uncontrolled) */
  defaultValue?: string;
  /** Change handler */
  onValueChange?: (value: string) => void;
  /** Required attribute */
  required?: boolean;
  /** Name for form submission */
  name?: string;
  /** Orientation */
  orientation?: 'horizontal' | 'vertical';
  /** Loop keyboard navigation */
  loop?: boolean;
  /** Children (RadioGroupItem components) */
  children: React.ReactNode;
}

/**
 * RadioGroup component props
 */
export type RadioGroupProps = OIDefaultProps &
  RadioGroupOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof RadioGroupOwnProps | 'className'>;

/**
 * RadioGroup component type
 */
export type RadioGroupComponent = React.ForwardRefExoticComponent<
  RadioGroupProps & { ref?: OIComponentRef<'div'> }
>;

/**
 * RadioGroupItem's own props
 */
export interface RadioGroupItemOwnProps {
  /** Value for this option */
  value: string;
  /** Disabled state */
  disabled?: boolean;
  /** Required state */
  required?: boolean;
  /** ID for label association */
  id?: string;
}

/**
 * RadioGroupItem component props
 */
export type RadioGroupItemProps = OIDefaultProps &
  RadioGroupItemOwnProps &
  Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, keyof RadioGroupItemOwnProps | 'className'>;

/**
 * RadioGroupItem component type
 */
export type RadioGroupItemComponent = React.ForwardRefExoticComponent<
  RadioGroupItemProps & { ref?: OIComponentRef<'button'> }
>;

/**
 * Default theme configuration for RadioGroup
 */
export const radioGroupDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'grid gap-2',
    variants: {
      size: {
        sm: 'gap-1.5',
        md: 'gap-2',
        lg: 'gap-3',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50',
        false: '',
      },
    },
  },
  slots: {
    item: {
      base: 'aspect-square rounded-full border border-border text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-border-focus disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary',
      variants: {
        size: {
          sm: 'h-4 w-4',
          md: 'h-5 w-5',
          lg: 'h-6 w-6',
        },
      },
      modifiers: {},
    },
    indicator: {
      base: 'flex items-center justify-center',
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
