/**
 * Banner component
 * @module components/banner
 */
import React, { useId, useMemo } from 'react';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { BannerActions } from './banner-actions';
import { BannerBody } from './banner-body';
import { BannerClose } from './banner-close';
import { BannerDescription } from './banner-description';
import { BannerTitle } from './banner-title';
import { BannerContext } from './banner.context';
import type { BannerComponent, BannerContextValue, BannerProps } from './types';
import { bannerDefaultTheme } from './types';

/**
 * Default variant icons
 */
const VariantIcons = {
  info: () => <Icon name="info" />,
  success: () => <Icon name="check_circle" />,
  warning: () => <Icon name="alert_triangle" />,
  error: () => <Icon name="alert_circle" />,
};

/**
 * Banner component
 *
 * A prominent message banner with support for different feedback states,
 * icons, and action buttons. Uses context to share ARIA IDs and dismiss handlers.
 *
 * @example
 * <Banner variant="info" dismissible onDismiss={handleDismiss}>
 *   <Banner.Title>New Feature</Banner.Title>
 *   <Banner.Description>
 *     We've added a new dashboard feature. Check it out!
 *   </Banner.Description>
 *   <Banner.Actions>
 *     <Button size="sm">Learn more</Button>
 *   </Banner.Actions>
 * </Banner>
 *
 * @example
 * <Banner variant="error" spotlight>
 *   <Banner.Title>Error</Banner.Title>
 *   <Banner.Description>
 *     Something went wrong. Please try again.
 *   </Banner.Description>
 * </Banner>
 */
const BannerRoot = React.forwardRef(function Banner<T extends React.ElementType = 'div'>(
  {
    component,
    className,
    children,
    ozid,
    variant = 'info',
    type = 'inline',
    spotlight,
    dismissible,
    icon,
    onDismiss,
    ...rest
  }: BannerProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('banner', bannerDefaultTheme);
  const Element = component ?? 'div';

  // Generate unique IDs for ARIA
  const uniqueId = useId();
  const titleId = `banner-title-${uniqueId}`;
  const descriptionId = `banner-description-${uniqueId}`;

  // Context value for sub-components
  const contextValue: BannerContextValue = useMemo(
    () => ({
      titleId,
      descriptionId,
      variant,
      onDismiss: dismissible ? onDismiss : undefined,
    }),
    [titleId, descriptionId, variant, dismissible, onDismiss],
  );

  // Default icon based on variant
  const DefaultIcon = VariantIcons[variant];
  const showDefaultIcon = !icon && DefaultIcon;

  return (
    <BannerContext.Provider value={contextValue}>
      <Element
        ref={ref}
        className={theme.root({ className, variant, type, spotlight, dismissible })}
        data-ozid={ozid}
        data-variant={variant}
        role="alert"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        {...rest}
      >
        {/* Icon slot */}
        {(icon || showDefaultIcon) && (
          <Slot
            baseOzid={ozid}
            className={theme.icon?.({ variant }) ?? ''}
            slotName="icon"
            slot={icon}
            component="span"
            aria-hidden="true"
          >
            {showDefaultIcon && <DefaultIcon />}
          </Slot>
        )}

        {/* Main content */}
        <div className={theme.content?.({}) ?? 'flex-1 min-w-0'}>{children}</div>

        {/* Close button (rendered via context) */}
        {dismissible && <BannerClose />}
      </Element>
    </BannerContext.Provider>
  );
}) as unknown as BannerComponent;

// Attach sub-components
BannerRoot.displayName = 'Banner';
BannerRoot.Title = BannerTitle;
BannerRoot.Description = BannerDescription;
BannerRoot.Body = BannerBody;
BannerRoot.Actions = BannerActions;
BannerRoot.Close = BannerClose;

export const Banner = BannerRoot;
