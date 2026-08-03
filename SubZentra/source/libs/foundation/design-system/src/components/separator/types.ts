/**
 * Separator component type definitions
 * @module components/separator/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Separator variant definitions
 */
export const SeparatorVariants = {
  orientation: ['horizontal', 'vertical'] as const,
} as const;

/**
 * Separator modifier definitions
 */
export const SeparatorModifiers = ['decorative'] as const;

/**
 * Separator slot definitions
 */
export const SeparatorSlots = [] as const;

/**
 * Separator's own props
 */
export interface SeparatorOwnProps
  extends OIComponentOwnProps<
    typeof SeparatorVariants,
    typeof SeparatorModifiers,
    typeof SeparatorSlots
  > {
  /** Orientation of the separator */
  orientation?: (typeof SeparatorVariants.orientation)[number];
  /** Whether the separator is purely decorative (no semantic meaning) */
  decorative?: boolean;
}

/**
 * Separator component props
 */
export type SeparatorProps<T extends React.ElementType = 'div'> = PolymorphicProps<
  T,
  SeparatorOwnProps
>;

/**
 * Separator component ref type
 */
export type SeparatorRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

/**
 * Separator component type
 */
export interface SeparatorComponent {
  <T extends React.ElementType = 'div'>(
    props: SeparatorProps<T> & { ref?: SeparatorRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Separator
 */
export const separatorDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'shrink-0 bg-border',
    variants: {
      orientation: {
        horizontal: 'h-px w-full',
        vertical: 'h-full w-px',
      },
    },
    modifiers: {
      decorative: {
        true: '',
        false: '',
      },
    },
  },
  slots: {},
  defaultVariants: {
    orientation: 'horizontal',
  },
};
