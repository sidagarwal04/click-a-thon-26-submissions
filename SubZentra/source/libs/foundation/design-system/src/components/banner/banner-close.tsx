/**
 * Banner.Close sub-component
 * @module components/banner
 */
import React from 'react';

import { Icon } from '@open-zentra/foundation-icons';

import { useTheme } from '../../theme';
import { useBannerContext } from './banner.context';
import type { BannerCloseProps } from './types';
import { bannerDefaultTheme } from './types';

/**
 * Banner.Close component
 *
 * Close button for dismissible banners. Uses context to access dismiss handler.
 */
export const BannerClose: React.FC<BannerCloseProps> = ({ className, ozid }) => {
  const theme = useTheme('banner', bannerDefaultTheme);
  const { variant, onDismiss } = useBannerContext();

  if (!onDismiss) {
    return null;
  }

  return (
    <button
      type="button"
      className={theme.close?.({ className, variant }) ?? className}
      onClick={onDismiss}
      aria-label="Dismiss banner"
      data-ozid={ozid}
      data-slot="close"
    >
      <Icon name="x" size="sm" />
    </button>
  );
};

BannerClose.displayName = 'Banner.Close';
