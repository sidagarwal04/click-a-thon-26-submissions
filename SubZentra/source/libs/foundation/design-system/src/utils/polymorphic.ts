/**
 * Polymorphic component utilities
 * @module utils/polymorphic
 */

import React from 'react';

/**
 * Gets the display name of a component
 *
 * @param component - React component or element type
 * @returns Display name string
 */
export function getDisplayName(component: React.ElementType): string {
  if (typeof component === 'string') {
    return component;
  }
  return component.displayName || component.name || 'Component';
}

/**
 * Creates a polymorphic component with proper ref forwarding
 * This is a helper to create components that can be rendered as different elements
 *
 * @example
 * const Button = createPolymorphicComponent<'button', ButtonProps>(
 *   'Button',
 *   (props, ref) => {
 *     const { component: Component = 'button', ...rest } = props;
 *     return <Component ref={ref} {...rest} />;
 *   }
 * );
 *
 * @param displayName - Display name for the component
 * @param render - Render function
 * @returns Polymorphic component
 */
export function createPolymorphicComponent<
  TDefaultElement extends React.ElementType,
  TProps extends object = object,
>(
  displayName: string,
  render: <T extends React.ElementType = TDefaultElement>(
    props: TProps & { component?: T } & Omit<React.ComponentPropsWithoutRef<T>, keyof TProps>,
    ref: React.ForwardedRef<Element>,
  ) => React.ReactNode,
) {
  const Component = React.forwardRef(
    render as unknown as React.ForwardRefRenderFunction<Element, Record<string, unknown>>,
  ) as unknown as (<T extends React.ElementType = TDefaultElement>(
    props: TProps & { component?: T } & Omit<React.ComponentPropsWithRef<T>, keyof TProps>,
  ) => React.ReactNode) & { displayName?: string };

  Component.displayName = displayName;

  return Component;
}

/**
 * Type helper for extracting props from a polymorphic component
 */
export type ExtractPolymorphicProps<
  TComponent extends React.ElementType,
  TProps extends object,
> = TProps & Omit<React.ComponentPropsWithoutRef<TComponent>, keyof TProps>;

/**
 * Type helper for extracting ref type from a polymorphic component
 */
export type ExtractPolymorphicRef<TComponent extends React.ElementType> =
  React.ComponentPropsWithRef<TComponent>['ref'];
