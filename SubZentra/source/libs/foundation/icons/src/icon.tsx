import React from 'react';

import clsx from 'clsx';

import { ICON_SIZE_MAPPER } from './constants';
import { getAllIconNames, getIcon } from './registry/registry';
import type { IconProps } from './types';

/**
 * Icon component that wraps lucide-react icons with Tailwind-driven sizing and styling
 *
 * @example
 * ```tsx
 * <Icon name="home" size="lg" className="text-blue-500" />
 * <Icon name="search" onClick={handleClick} aria-label="Search" />
 * ```
 */
export const Icon = React.forwardRef<HTMLElement, IconProps>(function Icon(
  {
    name,
    size = 'base',
    className,
    iconClassName,
    strokeWidth = 2,
    onClick,
    style,
    'data-testid': testId,
    'aria-label': ariaLabel,
    'aria-hidden': ariaHidden = true,
    ...rest
  },
  ref,
) {
  const IconComponent = getIcon(name);

  if (!IconComponent) {
    if (process.env.NODE_ENV !== 'production') {
      console.warn(
        `Icon "${name}" is not registered. Available icons: ${getAllIconNames().join(', ')}`,
      );
    }

    // Render a visible placeholder instead of silently returning null
    return (
      <i
        ref={ref}
        className={clsx(ICON_SIZE_MAPPER[size], 'flex justify-center items-center', className)}
        data-testid={testId}
        aria-label={ariaLabel}
        aria-hidden={ariaHidden && !ariaLabel ? true : undefined}
        title={process.env.NODE_ENV !== 'production' ? `Missing icon: ${name}` : undefined}
      >
        <svg
          className={clsx('w-full h-full', iconClassName)}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
        >
          <rect x="3" y="3" width="18" height="18" rx="2" opacity="0.3" />
          <line x1="9" y1="9" x2="15" y2="15" opacity="0.5" />
          <line x1="15" y1="9" x2="9" y2="15" opacity="0.5" />
        </svg>
      </i>
    );
  }

  return (
    <i
      ref={ref}
      className={clsx(ICON_SIZE_MAPPER[size], 'flex justify-center items-center', className)}
      onClick={onClick}
      style={style}
      data-testid={testId}
      aria-label={ariaLabel}
      aria-hidden={ariaHidden && !ariaLabel ? true : undefined}
      {...rest}
    >
      <IconComponent className={clsx('w-full h-full', iconClassName)} strokeWidth={strokeWidth} />
    </i>
  );
});

Icon.displayName = 'Icon';
