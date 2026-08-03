/**
 * Input component type definitions
 * @module components/input/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicRef,
} from '../../types';

/**
 * Input variant definitions
 */
export const InputVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Input modifier definitions
 */
export const InputModifiers = ['disabled', 'invalid', 'readOnly'] as const;

/**
 * Input slot definitions
 */
export const InputSlots = ['start', 'end'] as const;

/**
 * Input's own props
 */
export interface InputOwnProps extends OIDefaultProps {
  /** Input size variant */
  size?: (typeof InputVariants.size)[number];
  /** Disabled state */
  disabled?: boolean;
  /** Invalid/error state */
  invalid?: boolean;
  /** Read-only state */
  readOnly?: boolean;
  /** Start slot (icon or content before input) */
  start?: OIComponentSlotProps;
  /** End slot (icon or content after input) */
  end?: OIComponentSlotProps;
  /** Input type */
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url' | 'search';
  /** Placeholder text */
  placeholder?: string;
  /** Current value (controlled) */
  value?: string | number;
  /** Default value (uncontrolled) */
  defaultValue?: string | number;
  /** Change handler */
  onChange?: React.ChangeEventHandler<HTMLInputElement>;
  /** Name attribute for form submission */
  name?: string;
  /** ID for label association */
  id?: string;
  /** Aria-describedby for error messages */
  'aria-describedby'?: string;
  /** Required field */
  required?: boolean;
  /** Autocomplete attribute */
  autoComplete?: string;
  /** Autofocus on mount */
  autoFocus?: boolean;
  /** Min value for number inputs */
  min?: number | string;
  /** Max value for number inputs */
  max?: number | string;
  /** Step for number inputs */
  step?: number | string;
  /** Pattern for validation */
  pattern?: string;
  /** Max length */
  maxLength?: number;
  /** Min length */
  minLength?: number;
}

/**
 * Input component props
 */
export type InputProps = InputOwnProps &
  Omit<React.InputHTMLAttributes<HTMLInputElement>, keyof InputOwnProps | 'className'>;

/**
 * Input component ref type
 */
export type InputRef = PolymorphicRef<'input'>;

/**
 * Input component type
 */
export interface InputComponent {
  (props: InputProps & { ref?: InputRef }): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Input
 */
export const inputDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex w-full rounded-md border bg-background px-3 py-2 text-base transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
    variants: {
      size: {
        sm: 'h-8 text-sm px-2',
        md: 'h-10',
        lg: 'h-12 text-lg px-4',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 cursor-not-allowed',
        false: '',
      },
      invalid: {
        true: 'border-border-invalid focus-visible:ring-border-invalid',
        false: 'border-border focus-visible:ring-border-focus',
      },
      readOnly: {
        true: 'bg-background-muted cursor-default focus-visible:ring-0',
        false: '',
      },
    },
  },
  slots: {
    start: {
      base: 'absolute left-3 top-1/2 -translate-y-1/2 text-foreground-muted pointer-events-none',
      variants: {
        size: {
          sm: 'left-2',
          md: 'left-3',
          lg: 'left-4',
        },
      },
      modifiers: {},
    },
    end: {
      base: 'absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted',
      variants: {
        size: {
          sm: 'right-2',
          md: 'right-3',
          lg: 'right-4',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
