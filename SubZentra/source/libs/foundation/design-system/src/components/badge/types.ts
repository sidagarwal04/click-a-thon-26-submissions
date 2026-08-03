/**
 * Badge component type definitions
 * @module components/badge/types
 */

import type {
  ComponentThemeConfigStructure,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Badge variant definitions
 */
export const BadgeVariants = {
  intent: ['default', 'primary', 'secondary', 'success', 'warning', 'danger', 'info'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Badge modifier definitions
 */
export const BadgeModifiers = [] as const;

/**
 * Badge slot definitions
 */
export const BadgeSlots = [] as const;

/**
 * Badge's own props (manually defined for better control)
 */
export interface BadgeOwnProps extends OIDefaultProps {
  /** Badge intent/style variant */
  intent?: (typeof BadgeVariants.intent)[number];
  /** Badge size */
  size?: (typeof BadgeVariants.size)[number];
  /** Badge content */
  children?: React.ReactNode;
}

/**
 * Badge component props with polymorphism support
 */
export type BadgeProps<T extends React.ElementType = 'span'> = PolymorphicProps<T, BadgeOwnProps>;

/**
 * Badge component ref type
 */
export type BadgeRef<T extends React.ElementType = 'span'> = PolymorphicRef<T>;

/**
 * Badge component type (polymorphic with forwardRef)
 */
export interface BadgeComponent {
  <T extends React.ElementType = 'span'>(
    props: BadgeProps<T> & { ref?: BadgeRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Badge
 */
export const badgeDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-flex items-center rounded-full font-medium',
    variants: {
      intent: {
        default: 'bg-background-muted text-foreground',
        primary: 'bg-primary text-primary-foreground',
        secondary: 'bg-secondary text-secondary-foreground border border-border',
        success: 'bg-success text-success-foreground',
        warning: 'bg-warning text-warning-foreground',
        danger: 'bg-danger text-danger-foreground',
        info: 'bg-info text-info-foreground',
      },
      size: {
        sm: 'px-2 py-0.5 text-xs',
        md: 'px-2.5 py-0.5 text-sm',
        lg: 'px-3 py-1 text-base',
      },
    },
    modifiers: {},
  },
  defaultVariants: {
    intent: 'default',
    size: 'md',
  },
};
