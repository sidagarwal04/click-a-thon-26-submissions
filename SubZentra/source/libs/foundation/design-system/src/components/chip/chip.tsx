/**
 * Chip component
 * @module components/chip
 */
import React from 'react';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import type { ChipComponent, ChipProps } from './types';
import { chipDefaultTheme } from './types';

/**
 * Default close icon
 */
const DefaultCloseIcon = () => <Icon name="x" size="xs" />;

/**
 * Chip component
 *
 * A compact element for displaying tags, filters, or selected values.
 *
 * @example
 * // Basic chip
 * <Chip>React</Chip>
 *
 * @example
 * // With variant
 * <Chip variant="success">Completed</Chip>
 *
 * @example
 * // Removable chip
 * <Chip removable onRemove={() => handleRemove('tag')}>
 *   Removable Tag
 * </Chip>
 *
 * @example
 * // With start icon
 * <Chip start={<UserIcon />}>John Doe</Chip>
 *
 * @example
 * // Rounded (pill shape)
 * <Chip rounded>Pill Chip</Chip>
 */
export const Chip = React.forwardRef(function Chip<T extends React.ElementType = 'span'>(
  {
    component,
    className,
    children,
    ozid,
    variant = 'default',
    size = 'md',
    removable,
    rounded = true,
    disabled,
    start,
    close,
    onRemove,
    ...rest
  }: ChipProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('chip', chipDefaultTheme);
  const Element = component ?? 'span';

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!disabled && onRemove) {
      onRemove();
    }
  };

  return (
    <Element
      ref={ref}
      className={theme.root({ className, variant, size, removable, rounded, disabled })}
      data-ozid={ozid}
      data-variant={variant}
      aria-disabled={disabled || undefined}
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

      {/* Chip content */}
      <span className="truncate">{children}</span>

      {/* Close/Remove button */}
      {removable && (
        <Slot
          baseOzid={ozid}
          className={theme.close?.({ size, disabled }) ?? ''}
          slotName="close"
          slot={close}
          component="button"
          onClick={handleRemove}
          aria-label="Remove"
          type="button"
          disabled={disabled}
        >
          <DefaultCloseIcon />
        </Slot>
      )}
    </Element>
  );
}) as ChipComponent;

Chip.displayName = 'Chip';
