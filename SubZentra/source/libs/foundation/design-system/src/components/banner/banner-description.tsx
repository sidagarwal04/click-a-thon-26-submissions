/**
 * Banner.Description sub-component
 * @module components/banner
 */
import React from 'react';

import { useTheme } from '../../theme';
import { useBannerContext } from './banner.context';
import type { BannerDescriptionProps } from './types';
import { bannerDefaultTheme } from './types';

/**
 * Banner.Description component
 *
 * Description text for the banner. Uses context to provide proper ARIA description.
 */
export const BannerDescription: React.FC<BannerDescriptionProps> = ({
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('banner', bannerDefaultTheme);
  const { descriptionId, variant } = useBannerContext();

  return (
    <p
      id={descriptionId}
      className={theme.description?.({ className, variant }) ?? className}
      data-ozid={ozid}
      data-slot="description"
    >
      {children}
    </p>
  );
};

BannerDescription.displayName = 'Banner.Description';
