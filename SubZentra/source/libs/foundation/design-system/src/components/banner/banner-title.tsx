/**
 * Banner.Title sub-component
 * @module components/banner
 */
import React from 'react';

import { useTheme } from '../../theme';
import { useBannerContext } from './banner.context';
import type { BannerTitleProps } from './types';
import { bannerDefaultTheme } from './types';

/**
 * Banner.Title component
 *
 * Title text for the banner. Uses context to provide proper ARIA labeling.
 */
export const BannerTitle: React.FC<BannerTitleProps> = ({ children, className, ozid }) => {
  const theme = useTheme('banner', bannerDefaultTheme);
  const { titleId, variant } = useBannerContext();

  return (
    <div
      id={titleId}
      className={theme.title?.({ className, variant }) ?? className}
      data-ozid={ozid}
      data-slot="title"
    >
      {children}
    </div>
  );
};

BannerTitle.displayName = 'Banner.Title';
