/**
 * Banner.Body sub-component
 * @module components/banner
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { BannerBodyProps } from './types';
import { bannerDefaultTheme } from './types';

/**
 * Banner.Body component
 *
 * Container for custom body content in the banner
 */
export const BannerBody: React.FC<BannerBodyProps> = ({ children, className, ozid }) => {
  const theme = useTheme('banner', bannerDefaultTheme);

  return (
    <div className={theme.body?.({ className }) ?? className} data-ozid={ozid} data-slot="body">
      {children}
    </div>
  );
};

BannerBody.displayName = 'Banner.Body';
