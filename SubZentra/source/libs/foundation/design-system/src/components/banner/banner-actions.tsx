/**
 * Banner.Actions sub-component
 * @module components/banner
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { BannerActionsProps } from './types';
import { bannerDefaultTheme } from './types';

/**
 * Banner.Actions component
 *
 * Container for action buttons in the banner
 */
export const BannerActions: React.FC<BannerActionsProps> = ({ children, className, ozid }) => {
  const theme = useTheme('banner', bannerDefaultTheme);

  return (
    <div
      className={theme.actions?.({ className }) ?? className}
      data-ozid={ozid}
      data-slot="actions"
    >
      {children}
    </div>
  );
};

BannerActions.displayName = 'Banner.Actions';
