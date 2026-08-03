/**
 * Textarea component type definitions
 * @module components/textarea/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentRef,
  OIDefaultProps,
} from '../../types';

/**
 * Textarea variant definitions
 */
export const TextareaVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Textarea modifier definitions
 */
export const TextareaModifiers = ['disabled', 'invalid', 'readOnly'] as const;

/**
 * Textarea slot definitions
 */
export const TextareaSlots = [] as const;

/**
 * Textarea's own props
 */
export interface TextareaOwnProps
  extends OIComponentOwnProps<
    typeof TextareaVariants,
    typeof TextareaModifiers,
    typeof TextareaSlots
  > {
  /** Placeholder text */
  placeholder?: string;
  /** Current value (controlled) */
  value?: string;
  /** Default value (uncontrolled) */
  defaultValue?: string;
  /** Change handler */
  onChange?: React.ChangeEventHandler<HTMLTextAreaElement>;
  /** Name attribute for form submission */
  name?: string;
  /** ID for label association */
  id?: string;
  /** Aria-describedby for error messages */
  'aria-describedby'?: string;
  /** Required field */
  required?: boolean;
  /** Number of rows */
  rows?: number;
  /** Max length */
  maxLength?: number;
  /** Min length */
  minLength?: number;
  /** Auto resize */
  autoResize?: boolean;
}

/**
 * Textarea component props
 */
export type TextareaProps = OIDefaultProps &
  TextareaOwnProps &
  Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, keyof TextareaOwnProps | 'className'>;

/**
 * Textarea component type
 */
export type TextareaComponent = React.ForwardRefExoticComponent<
  TextareaProps & { ref?: OIComponentRef<'textarea'> }
>;

/**
 * Default theme configuration for Textarea
 */
export const textareaDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex w-full rounded-md border bg-background px-3 py-2 text-base transition-colors placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 resize-y min-h-[80px]',
    variants: {
      size: {
        sm: 'text-sm px-2 py-1.5',
        md: '',
        lg: 'text-lg px-4 py-3',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 cursor-not-allowed resize-none',
        false: '',
      },
      invalid: {
        true: 'border-border-invalid focus-visible:ring-border-invalid',
        false: 'border-border focus-visible:ring-border-focus',
      },
      readOnly: {
        true: 'bg-background-muted cursor-default focus-visible:ring-0 resize-none',
        false: '',
      },
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
