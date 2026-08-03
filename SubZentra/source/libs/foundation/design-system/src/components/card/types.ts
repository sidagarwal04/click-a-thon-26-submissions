/**
 * Card component type definitions
 * @module components/card/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Card variant definitions
 */
export const CardVariants = {
  padding: ['none', 'sm', 'md', 'lg'] as const,
} as const;

/**
 * Card modifier definitions
 */
export const CardModifiers = ['emphasis'] as const;

/**
 * Card slot definitions
 */
export const CardSlots = [] as const;

/**
 * Card's own props
 */
export interface CardOwnProps
  extends OIComponentOwnProps<typeof CardVariants, typeof CardModifiers, typeof CardSlots> {
  /** Inner padding */
  padding?: (typeof CardVariants.padding)[number];
  /** Draw the card with an accent border rather than the default line */
  emphasis?: boolean;
  /** Children content */
  children?: React.ReactNode;
}

/**
 * Card component props
 */
export type CardProps<T extends React.ElementType = 'section'> = PolymorphicProps<T, CardOwnProps>;

/**
 * Card component ref type
 */
export type CardRef<T extends React.ElementType = 'section'> = PolymorphicRef<T>;

// Sub-component props
export interface CardHeaderProps extends OIDefaultProps {
  /** Leading icon */
  icon?: OIComponentSlotProps;
  /** Trailing content, aligned to the far edge of the header row */
  end?: OIComponentSlotProps;
  children?: React.ReactNode;
}

export interface CardTitleProps extends OIDefaultProps {
  children?: React.ReactNode;
}

/**
 * Card component type with sub-components
 */
export interface CardComponent {
  <T extends React.ElementType = 'section'>(
    props: CardProps<T> & { ref?: CardRef<T> },
  ): React.ReactNode;
  displayName?: string;
  Header: React.FC<CardHeaderProps>;
  Title: React.FC<CardTitleProps>;
}

/**
 * Default theme configuration for Card
 */
export const cardDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex flex-col bg-card border border-border rounded-sm',
    variants: {
      padding: {
        none: 'p-0',
        sm: 'p-3',
        md: 'p-5',
        lg: 'p-7',
      },
    },
    modifiers: {
      emphasis: {
        true: 'border-primary',
        false: '',
      },
    },
  },
  slots: {
    header: {
      base: 'flex items-center gap-2 mb-4',
      variants: {},
      modifiers: {},
    },
    headerIcon: {
      base: 'shrink-0 text-primary [&>svg]:h-4 [&>svg]:w-4',
      variants: {},
      modifiers: {},
    },
    headerEnd: {
      base: 'ml-auto',
      variants: {},
      modifiers: {},
    },
    title: {
      base: 'font-mono text-xs font-semibold uppercase tracking-[0.14em] text-foreground',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    padding: 'md',
  },
};
