/**
 * Avatar component
 * @module components/avatar
 */
import React, { useState } from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { getInitials } from './avatar-utils';
import type { AvatarComponent, AvatarProps } from './types';
import { avatarDefaultTheme } from './types';

/**
 * Avatar component
 *
 * Displays a user avatar with support for images, initials fallback, status indicators,
 * and context icons.
 *
 * @example
 * // With image
 * <Avatar src="/avatar.jpg" alt="John Doe" />
 *
 * @example
 * // With initials fallback
 * <Avatar name="John Doe" />
 *
 * @example
 * // With status indicator
 * <Avatar src="/avatar.jpg" status="online" />
 *
 * @example
 * // With context icon
 * <Avatar
 *   src="/avatar.jpg"
 *   context={<Icon name="verified" />}
 * />
 *
 * @example
 * // Different sizes
 * <Avatar src="/avatar.jpg" size="xs" />
 * <Avatar src="/avatar.jpg" size="md" />
 * <Avatar src="/avatar.jpg" size="2xl" />
 */
export const Avatar = React.forwardRef(function Avatar<T extends React.ElementType = 'div'>(
  {
    component,
    className,
    ozid,
    size = 'md',
    shape = 'circle',
    status = 'none',
    src,
    alt,
    name,
    skeleton,
    context,
    hasContext: hasContextProp,
    fallback,
    onError,
    ...rest
  }: AvatarProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('avatar', avatarDefaultTheme);
  const Element = component ?? 'div';
  const [imageError, setImageError] = useState(false);

  const handleImageError = () => {
    setImageError(true);
    onError?.();
  };

  const showImage = src && !imageError && !skeleton;
  const showFallback = !showImage && !skeleton;
  const initials = name ? getInitials(name) : '';
  const hasContext = hasContextProp ?? Boolean(context);

  return (
    <Element
      ref={ref}
      className={theme.root({ className, size, shape, status, skeleton, hasContext })}
      data-ozid={ozid}
      data-status={status !== 'none' ? status : undefined}
      {...rest}
    >
      {/* Image */}
      {showImage && (
        <img
          src={src}
          alt={alt || name || 'Avatar'}
          className={theme.image?.({ size, shape }) ?? ''}
          onError={handleImageError}
          data-ozid={ozid ? `${ozid}__image` : undefined}
        />
      )}

      {/* Fallback (initials or custom) */}
      {showFallback && (
        <Slot
          baseOzid={ozid}
          className={theme.fallback?.({ size }) ?? ''}
          slotName="fallback"
          slot={fallback}
          component="span"
        >
          {initials || (
            <svg
              className="h-[60%] w-[60%]"
              fill="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
            </svg>
          )}
        </Slot>
      )}

      {/* Status indicator */}
      {status !== 'none' && !context && (
        <span
          className={theme.statusIndicator?.({ size, status }) ?? ''}
          data-ozid={ozid ? `${ozid}__status` : undefined}
          aria-label={`Status: ${status}`}
        />
      )}

      {/* Context slot (replaces status indicator position) */}
      {context && (
        <Slot
          baseOzid={ozid}
          className={theme.context?.({ size }) ?? ''}
          slotName="context"
          slot={context}
          component="span"
        />
      )}
    </Element>
  );
}) as AvatarComponent;

Avatar.displayName = 'Avatar';
