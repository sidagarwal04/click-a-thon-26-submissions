/**
 * IconButton component
 * @module components/icon-button
 */
import React from 'react';

import { useTheme } from '../../theme';
import { Spinner } from '../spinner';
import type { IconButtonComponent, IconButtonProps } from './types';
import { iconButtonDefaultTheme } from './types';

/**
 * IconButton component
 *
 * A button designed for icon-only actions. Requires aria-label for accessibility.
 *
 * @example
 * <IconButton aria-label="Close menu">
 *   <CloseIcon />
 * </IconButton>
 *
 * @example
 * <IconButton aria-label="Search" size="lg" intent="primary">
 *   <SearchIcon />
 * </IconButton>
 */
const IconButtonImpl = <T extends React.ElementType = 'button'>(
  {
    component,
    className,
    children,
    ozid,
    intent = 'secondary',
    size = 'md',
    disabled,
    loading,
    'aria-label': ariaLabel,
    ...rest
  }: IconButtonProps<T>,
  ref: React.ForwardedRef<Element>,
) => {
  const theme = useTheme('iconButton', iconButtonDefaultTheme);
  const Element = component ?? 'button';

  // Boolean(), not `||`: with disabled={false} and loading unset this yields
  // undefined, and the theme resolver only applies a modifier for an actual
  // boolean — so the modifier's `false` class would silently never apply.
  const isDisabled = Boolean(disabled || loading);
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
      })}
      data-ozid={ozid}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      aria-label={ariaLabel}
      disabled={Element === 'button' ? isDisabled : undefined}
      type={Element === 'button' ? 'button' : undefined}
      {...rest}
    >
      {loading ? (
        <Spinner size={spinnerSize} aria-label="Loading" />
      ) : (
        <span className={theme.icon?.({ size }) ?? ''} aria-hidden="true">
          {children}
        </span>
      )}
    </Element>
  );
};

export const IconButton = React.forwardRef(
  IconButtonImpl as unknown as React.ForwardRefRenderFunction<Element, Record<string, unknown>>,
) as unknown as IconButtonComponent;

IconButton.displayName = 'IconButton';
