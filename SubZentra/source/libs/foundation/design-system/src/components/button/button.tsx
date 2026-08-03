/**
 * Button component
 * @module components/button
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { VisuallyHidden } from '../../primitives/visually-hidden';
import { useTheme } from '../../theme';
import { Spinner } from '../spinner';
import type { ButtonComponent, ButtonProps } from './types';
import { buttonDefaultTheme } from './types';

/**
 * Button component
 *
 * A versatile button component with multiple intents, sizes, and loading states.
 * Supports polymorphism, slots for icons, and comprehensive accessibility features.
 *
 * @example
 * // Primary button
 * <Button intent="primary">Click me</Button>
 *
 * @example
 * // With loading state
 * <Button loading>Submitting...</Button>
 *
 * @example
 * // With icons
 * <Button start={<PlusIcon />}>Add Item</Button>
 *
 * @example
 * // As a link
 * <Button component="a" href="/path">Go to page</Button>
 */
export const Button = React.forwardRef(function Button<T extends React.ElementType = 'button'>(
  {
    component,
    className,
    children,
    ozid,
    intent = 'primary',
    size = 'md',
    disabled,
    loading,
    fullWidth,
    start,
    end,
    loadingIndicator,
    'aria-label': ariaLabel,
    ...rest
  }: ButtonProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('button', buttonDefaultTheme);
  const Element = component ?? 'button';

  // Effective disabled state includes loading
  // Boolean(), not `||`: with disabled={false} and loading unset this yields
  // undefined, and the theme resolver only applies a modifier for an actual
  // boolean — so the modifier's `false` class would silently never apply.
  const isDisabled = Boolean(disabled || loading);

  // Map size to spinner size
  const spinnerSize = size === 'lg' ? 'md' : size === 'md' ? 'sm' : 'xs';

  return (
    <Element
      ref={ref}
      className={theme.root({
        className,
        intent,
        size,
        disabled: isDisabled,
        loading,
        fullWidth,
      })}
      data-ozid={ozid}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      aria-label={ariaLabel}
      disabled={Element === 'button' ? isDisabled : undefined}
      type={Element === 'button' ? 'button' : undefined}
      {...rest}
    >
      {/* Loading indicator */}
      {loading && (
        <Slot
          baseOzid={ozid}
          className={theme.loadingIndicator?.({ intent, size }) ?? ''}
          slotName="loadingIndicator"
          slot={loadingIndicator}
          component="span"
          aria-hidden="true"
        >
          <Spinner size={spinnerSize} aria-hidden="true" />
        </Slot>
      )}

      {/* Start slot */}
      {start && !loading && (
        <Slot
          baseOzid={ozid}
          className={theme.start?.({ intent, size }) ?? ''}
          slotName="start"
          slot={start}
          component="span"
          aria-hidden="true"
        />
      )}

      {/* Content */}
      {loading ? (
        <>
          <VisuallyHidden>Loading</VisuallyHidden>
          <span aria-hidden="true" className="opacity-0">
            {children}
          </span>
        </>
      ) : (
        children
      )}

      {/* End slot */}
      {end && !loading && (
        <Slot
          baseOzid={ozid}
          className={theme.end?.({ intent, size }) ?? ''}
          slotName="end"
          slot={end}
          component="span"
          aria-hidden="true"
        />
      )}
    </Element>
  );
}) as ButtonComponent;

Button.displayName = 'Button';
