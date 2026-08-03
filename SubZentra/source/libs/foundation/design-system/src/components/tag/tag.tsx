/**
 * Tag component
 * @module components/tag
 */
import React from 'react';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import type { TagComponent, TagProps } from './types';
import { tagDefaultTheme } from './types';

/**
 * Default dismiss icon
 */
const DefaultDismissIcon = () => <Icon name="x" size="xs" />;

/**
 * Tag component
 *
 * A label with optional dismiss functionality for representing items.
 *
 * @example
 * <Tag intent="primary">React</Tag>
 *
 * @example
 * // With start icon
 * <Tag start={<UserIcon />}>User Tag</Tag>
 *
 * @example
 * // Dismissible
 * <Tag dismissible onDismiss={() => removeTag('react')}>React</Tag>
 *
 * @example
 * // Custom end slot
 * <Tag end={<CustomButton />}>Custom</Tag>
 */
export const Tag = React.forwardRef(function Tag<T extends React.ElementType = 'span'>(
  {
    component,
    className,
    children,
    ozid,
    intent = 'default',
    size = 'md',
    dismissible,
    start,
    end,
    onDismiss,
    ...rest
  }: TagProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('tag', tagDefaultTheme);
  const Element = component ?? 'span';

  // Default end slot to dismiss button when dismissible
  const endSlot = dismissible && !end ? { children: <DefaultDismissIcon /> } : end;

  return (
    <Element
      ref={ref}
      className={theme.root({ className, intent, size, dismissible })}
      data-ozid={ozid}
      {...rest}
    >
      {/* Start slot */}
      {start && (
        <Slot
          baseOzid={ozid}
          className={theme.start?.({ size }) ?? ''}
          slotName="start"
          slot={start}
          component="span"
          aria-hidden="true"
        />
      )}

      {children}

      {/* End slot (dismiss button or custom content) */}
      {(dismissible || end) && (
        <Slot
          baseOzid={ozid}
          className={theme.end?.({ size }) ?? ''}
          slotName="end"
          slot={endSlot}
          component="button"
          onClick={dismissible ? onDismiss : undefined}
          aria-label={dismissible ? 'Dismiss' : undefined}
          type={dismissible ? 'button' : undefined}
        >
          {dismissible && !end && <DefaultDismissIcon />}
        </Slot>
      )}
    </Element>
  );
}) as TagComponent;

Tag.displayName = 'Tag';
