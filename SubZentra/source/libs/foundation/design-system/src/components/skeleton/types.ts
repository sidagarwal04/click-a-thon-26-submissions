/**
 * Skeleton component type definitions
 * @module components/skeleton/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentProps,
  OIComponentRef,
  OIDefaultProps,
} from '../../types';

/**
 * Skeleton variant definitions
 */
export const SkeletonVariants = {} as const;

/**
 * Skeleton modifier definitions
 */
export const SkeletonModifiers = ['animated'] as const;

/**
 * Skeleton slot definitions
 */
export const SkeletonSlots = [] as const;

/**
 * Skeleton's own props
 */
export interface SkeletonOwnProps
  extends OIComponentOwnProps<
    typeof SkeletonVariants,
    typeof SkeletonModifiers,
    typeof SkeletonSlots
  > {
  /** Width of the skeleton */
  width?: string | number;
  /** Height of the skeleton */
  height?: string | number;
  /** Border radius - 'none' | 'sm' | 'md' | 'lg' | 'full' */
  radius?: 'none' | 'sm' | 'md' | 'lg' | 'full';
}

/**
 * Skeleton component props
 */
export type SkeletonProps<T extends React.ElementType = 'div'> = OIComponentProps<
  T,
  SkeletonOwnProps & OIDefaultProps
>;

/**
 * Skeleton component type
 */
export type SkeletonComponent = <T extends React.ElementType = 'div'>(
  props: SkeletonProps<T> & { ref?: OIComponentRef<T> },
) => React.ReactNode;

/**
 * Default theme configuration for Skeleton
 */
export const skeletonDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'bg-background-muted',
    variants: {},
    modifiers: {
      animated: {
        true: 'animate-pulse',
        false: '',
      },
    },
  },
  defaultVariants: {},
};
