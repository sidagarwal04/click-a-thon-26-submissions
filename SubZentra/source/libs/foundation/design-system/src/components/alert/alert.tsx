/**
 * Alert component
 * @module components/alert
 */
import React from 'react';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import type { AlertComponent, AlertProps } from './types';
import { alertDefaultTheme } from './types';

/**
 * Default dismiss icon
 */
const DefaultDismissIcon = () => <Icon name="x" size="sm" />;

/**
 * Default alert icons by intent
 */
const DefaultAlertIcons = {
  info: () => <Icon name="info" size="base" />,
  success: () => <Icon name="check_circle" size="base" />,
  warning: () => <Icon name="alert_triangle" size="base" />,
  error: () => <Icon name="x_circle" size="base" />,
};

/**
 * Alert component
 *
 * A prominent message component for displaying important information.
 *
 * @example
 * // Basic info alert
 * <Alert intent="info">This is an informational message.</Alert>
 *
 * @example
 * // Success alert with title
 * <Alert intent="success" title="Success!">
 *   Your changes have been saved.
 * </Alert>
 *
 * @example
 * // Dismissible error alert
 * <Alert intent="error" dismissible onDismiss={() => setShow(false)}>
 *   Something went wrong.
 * </Alert>
 *
 * @example
 * // Custom start icon
 * <Alert start={<CustomIcon />}>Custom icon alert</Alert>
 */
export const Alert = React.forwardRef(function Alert<T extends React.ElementType = 'div'>(
  {
    component,
    className,
    children,
    ozid,
    intent = 'info',
    dismissible,
    start,
    end,
    title,
    onDismiss,
    ...rest
  }: AlertProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('alert', alertDefaultTheme);
  const Element = component ?? 'div';

  // Default start slot to intent-specific icon
  const DefaultIcon = DefaultAlertIcons[intent];
  const startSlot = start ?? { children: <DefaultIcon /> };

  // Default end slot to dismiss button when dismissible
  const endSlot = dismissible && !end ? { children: <DefaultDismissIcon /> } : end;

  return (
    <Element
      ref={ref}
      role="alert"
      className={theme.root({ className, intent, dismissible })}
      data-ozid={ozid}
      {...rest}
    >
      {/* Start slot (icon) */}
      <Slot
        baseOzid={ozid}
        className={theme.start?.({ intent }) ?? ''}
        slotName="start"
        slot={startSlot}
        component="span"
        aria-hidden="true"
      />
      {/* Content */}
      <div className="flex-1">
        {title && <div className="font-medium mb-1">{title}</div>}
        {children && <div className="text-sm opacity-90">{children}</div>}
      </div>
      {/* End slot (dismiss button or custom content) */}
      {(dismissible || end) && (
        <Slot
          baseOzid={ozid}
          className={theme.end?.({ intent }) ?? ''}
          slotName="end"
          slot={endSlot}
          component="button"
          onClick={dismissible ? onDismiss : undefined}
          aria-label={dismissible ? 'Dismiss alert' : undefined}
          type={dismissible ? 'button' : undefined}
        />
      )}
    </Element>
  );
}) as AlertComponent;

Alert.displayName = 'Alert';
