/**
 * Tag component type definitions
 * @module components/tag/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Tag variant definitions
 */
export const TagVariants = {
  intent: ['default', 'primary', 'secondary', 'success', 'warning', 'danger', 'info'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Tag modifier definitions
 */
export const TagModifiers = ['dismissible'] as const;

/**
 * Tag slot definitions
 */
export const TagSlots = ['start', 'end'] as const;

/**
 * Tag's own props
 */
export interface TagOwnProps extends OIDefaultProps {
  /** Tag intent/style variant */
  intent?: (typeof TagVariants.intent)[number];
  /** Tag size */
  size?: (typeof TagVariants.size)[number];
  /** Dismissible state */
  dismissible?: boolean;
  /** Start slot (icon or content before text) */
  start?: OIComponentSlotProps;
  /** End slot (dismiss button or custom content) */
  end?: OIComponentSlotProps;
  /** Tag content */
  children?: React.ReactNode;
  /** Called when dismiss button is clicked */
  onDismiss?: () => void;
}

/**
 * Tag component props
 */
export type TagProps<T extends React.ElementType = 'span'> = PolymorphicProps<T, TagOwnProps>;

/**
 * Tag component ref type
 */
export type TagRef<T extends React.ElementType = 'span'> = PolymorphicRef<T>;

/**
 * Tag component type
 */
export interface TagComponent {
  <T extends React.ElementType = 'span'>(props: TagProps<T> & { ref?: TagRef<T> }): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Tag
 */
export const tagDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-flex items-center gap-1 rounded-md font-medium',
    variants: {
      intent: {
        default: 'bg-background-muted text-foreground',
        primary: 'bg-primary/10 text-primary border border-primary/20',
        secondary: 'bg-secondary text-secondary-foreground border border-border',
        success: 'bg-success/10 text-success border border-success/20',
        warning: 'bg-warning/10 text-warning-foreground border border-warning/20',
        danger: 'bg-danger/10 text-danger border border-danger/20',
        info: 'bg-info/10 text-info border border-info/20',
      },
      size: {
        sm: 'px-2 py-0.5 text-xs',
        md: 'px-2.5 py-1 text-sm',
        lg: 'px-3 py-1.5 text-base',
      },
    },
    modifiers: {
      dismissible: {
        true: 'pr-1',
        false: '',
      },
    },
  },
  slots: {
    start: {
      base: 'shrink-0',
      variants: {
        size: {
          sm: 'h-3 w-3',
          md: 'h-4 w-4',
          lg: 'h-5 w-5',
        },
      },
      modifiers: {},
    },
    end: {
      base: 'shrink-0 rounded-sm opacity-70 hover:opacity-100 transition-opacity cursor-pointer',
      variants: {
        size: {
          sm: 'h-3 w-3 ml-0.5',
          md: 'h-4 w-4 ml-1',
          lg: 'h-5 w-5 ml-1.5',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    intent: 'default',
    size: 'md',
  },
};
