/**
 * Polymorphic component type definitions
 * Enables components to render as different HTML elements or React components
 * @module types/polymorphic
 */

import type { PropsOf } from './utils';

const POLYMORPHIC_RESERVED_PROP = {
  COMPONENT: 'component',
  REF: 'ref',
} as const;

type PolymorphicReservedProp =
  (typeof POLYMORPHIC_RESERVED_PROP)[keyof typeof POLYMORPHIC_RESERVED_PROP];

/**
 * The ref type for polymorphic components
 */
export type PolymorphicRef<T extends React.ElementType> = React.ComponentPropsWithRef<T>['ref'];

/**
 * Props that allow changing the rendered element
 */
export interface PolymorphicComponentProp<T extends React.ElementType> {
  /**
   * The component or HTML element to render as
   * @example component="a" // renders as anchor
   * @example component={Link} // renders as custom Link component
   */
  component?: T;
}

/**
 * Returns type-safe polymorphic component props
 * Merges component's own props with the target element's props
 */
export type PolymorphicProps<
  T extends React.ElementType = React.ElementType,
  TProps = object,
> = PolymorphicComponentProp<T> &
  TProps &
  Omit<PropsOf<T>, keyof TProps | PolymorphicReservedProp> & {
    ref?: PolymorphicRef<T>;
  };

/**
 * Type for a polymorphic component that can be rendered as different elements
 */
export type PolymorphicComponent<TDefaultElement extends React.ElementType, TProps = object> = <
  T extends React.ElementType = TDefaultElement,
>(
  props: PolymorphicProps<T, TProps>,
) => React.ReactNode;

/**
 * Type for a polymorphic component with forwardRef support
 */
export type PolymorphicForwardRefComponent<
  TDefaultElement extends React.ElementType,
  TProps = object,
> = <T extends React.ElementType = TDefaultElement>(
  props: PolymorphicProps<T, TProps> & { ref?: PolymorphicRef<T> },
) => React.ReactNode;

/**
 * Props for overridable components (internal use)
 */
export type OverridableComponentProps<
  T extends React.ElementType,
  TProps = object,
> = PolymorphicProps<T, TProps>;
