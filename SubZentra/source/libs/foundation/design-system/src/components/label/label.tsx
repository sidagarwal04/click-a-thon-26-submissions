/**
 * Label component
 * @module components/label
 */
import React from 'react';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { Tooltip } from '../tooltip';
import type { LabelComponent, LabelProps } from './types';
import { labelDefaultTheme } from './types';

/**
 * Default tooltip icon
 */
const DefaultTooltipIcon = () => <Icon name="help_circle" size="xs" />;

/**
 * Label component
 *
 * A form label with support for required indicators, tooltips, icons, and descriptions.
 *
 * @example
 * // Basic label
 * <Label htmlFor="email">Email Address</Label>
 *
 * @example
 * // Required field
 * <Label htmlFor="name" required>Name</Label>
 *
 * @example
 * // With tooltip
 * <Label htmlFor="password" tooltip="Must be at least 8 characters">
 *   Password
 * </Label>
 *
 * @example
 * // With description
 * <Label
 *   htmlFor="bio"
 *   description="Write a short bio about yourself"
 * >
 *   Biography
 * </Label>
 *
 * @example
 * // With icon
 * <Label htmlFor="email" icon={<MailIcon />}>
 *   Email
 * </Label>
 */
export const Label = React.forwardRef(function Label<T extends React.ElementType = 'label'>(
  {
    component,
    className,
    children,
    ozid,
    size = 'md',
    required,
    disabled,
    error,
    icon,
    requiredIndicator,
    tooltip,
    tooltipContent,
    description,
    htmlFor,
    ...rest
  }: LabelProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('label', labelDefaultTheme);
  const Element = component ?? 'label';
  const descriptionId = htmlFor ? `${htmlFor}-description` : undefined;

  return (
    <Element
      ref={ref}
      className={theme.root({ className, size, required, disabled, error })}
      data-ozid={ozid}
      htmlFor={Element === 'label' ? htmlFor : undefined}
      {...rest}
    >
      {/* Main label row */}
      <span className={theme.labelRow?.({ size }) ?? ''}>
        {/* Icon slot */}
        {icon && (
          <Slot
            baseOzid={ozid}
            className={theme.icon?.({ size }) ?? ''}
            slotName="icon"
            slot={icon}
            component="span"
            aria-hidden="true"
          />
        )}

        {/* Label text */}
        <span className={theme.text?.({ size, disabled, error }) ?? ''}>{children}</span>

        {/* Required indicator */}
        {required && (
          <Slot
            baseOzid={ozid}
            className={theme.requiredIndicator?.({ size }) ?? ''}
            slotName="requiredIndicator"
            slot={requiredIndicator}
            component="span"
            aria-hidden="true"
          >
            *
          </Slot>
        )}

        {/* Tooltip */}
        {tooltip && (
          <Tooltip content={tooltip}>
            <Slot
              baseOzid={ozid}
              className={theme.tooltipTrigger?.({ size }) ?? ''}
              slotName="tooltipContent"
              slot={tooltipContent}
              component="span"
              tabIndex={0}
            >
              <DefaultTooltipIcon />
            </Slot>
          </Tooltip>
        )}
      </span>

      {/* Description */}
      {description && (
        <Slot
          baseOzid={ozid}
          className={theme.description?.({ size, error }) ?? ''}
          slotName="description"
          slot={description}
          component="span"
          id={descriptionId}
        >
          {typeof description === 'string' ? description : null}
        </Slot>
      )}
    </Element>
  );
}) as LabelComponent;

Label.displayName = 'Label';
