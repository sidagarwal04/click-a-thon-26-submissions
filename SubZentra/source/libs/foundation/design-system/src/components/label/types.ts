/**
 * Label component type definitions
 * @module components/label/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Label variant definitions
 */
export const LabelVariants = {
  size: ['sm', 'md'] as const,
} as const;

/**
 * Label modifier definitions
 */
export const LabelModifiers = ['required', 'disabled', 'error'] as const;

/**
 * Label slot definitions
 */
export const LabelSlots = ['icon', 'requiredIndicator', 'tooltipContent', 'description'] as const;

/**
 * Label's own props
 */
export interface LabelOwnProps
  extends OIComponentOwnProps<typeof LabelVariants, typeof LabelModifiers, typeof LabelSlots> {
  /** Size of the label */
  size?: (typeof LabelVariants.size)[number];
  /** Whether the field is required */
  required?: boolean;
  /** Whether the field is disabled */
  disabled?: boolean;
  /** Whether the field has an error */
  error?: boolean;
  /** Icon displayed before the label text */
  icon?: OIComponentSlotProps;
  /** Custom required indicator (default is asterisk) */
  requiredIndicator?: OIComponentSlotProps;
  /** Tooltip content for additional information */
  tooltip?: React.ReactNode;
  /** Custom tooltip trigger content */
  tooltipContent?: OIComponentSlotProps;
  /** Description text below the label */
  description?: OIComponentSlotProps;
  /** ID of the form field this label is for */
  htmlFor?: string;
  /** Label text content */
  children?: React.ReactNode;
}

/**
 * Label component props
 */
export type LabelProps<T extends React.ElementType = 'label'> = PolymorphicProps<T, LabelOwnProps>;

/**
 * Label component ref type
 */
export type LabelRef<T extends React.ElementType = 'label'> = PolymorphicRef<T>;

/**
 * Label component type
 */
export interface LabelComponent {
  <T extends React.ElementType = 'label'>(
    props: LabelProps<T> & { ref?: LabelRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Label
 */
export const labelDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-flex flex-col gap-1',
    variants: {
      size: {
        sm: '',
        md: '',
      },
    },
    modifiers: {
      required: {
        true: '',
        false: '',
      },
      disabled: {
        true: 'opacity-50 cursor-not-allowed',
        false: '',
      },
      error: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    labelRow: {
      base: 'inline-flex items-center gap-1.5',
      variants: {
        size: {
          sm: '',
          md: '',
        },
      },
      modifiers: {},
    },
    icon: {
      base: 'shrink-0 text-muted-foreground',
      variants: {
        size: {
          sm: '[&>svg]:h-3.5 [&>svg]:w-3.5',
          md: '[&>svg]:h-4 [&>svg]:w-4',
        },
      },
      modifiers: {},
    },
    text: {
      base: 'font-medium text-foreground',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
        },
      },
      modifiers: {
        disabled: {
          true: 'text-muted-foreground',
          false: '',
        },
        error: {
          true: 'text-destructive',
          false: '',
        },
      },
    },
    requiredIndicator: {
      base: 'text-destructive',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
        },
      },
      modifiers: {},
    },
    tooltipTrigger: {
      base: 'inline-flex items-center justify-center rounded-full text-muted-foreground hover:text-foreground cursor-help',
      variants: {
        size: {
          sm: 'h-3.5 w-3.5 [&>svg]:h-3 [&>svg]:w-3',
          md: 'h-4 w-4 [&>svg]:h-3.5 [&>svg]:w-3.5',
        },
      },
      modifiers: {},
    },
    description: {
      base: 'text-muted-foreground',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-xs',
        },
      },
      modifiers: {
        error: {
          true: 'text-destructive',
          false: '',
        },
      },
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
