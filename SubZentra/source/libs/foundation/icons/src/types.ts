import type { LucideIcon } from 'lucide-react';

import type { IconSizeType } from './constants';
import type { IconName } from './registry/registry';

/**
 * Props for the Icon component
 */
export interface IconProps {
  /**
   * Name of the icon to render (must be registered in the icon registry)
   */
  name: IconName;
  /**
   * Size of the icon (maps to width & height classes)
   *
   * @default 'base'
   * @link https://tailwindcss.com/docs/width
   */
  size?: IconSizeType;
  /**
   * Additional CSS classes for the wrapper element
   * Use this for colors and custom styling
   *
   * @example
   * <Icon name="home" className="text-blue-500" />
   */
  className?: string;
  /**
   * Pass custom classes to the SVG element directly
   * Can be used to control deeply nested properties, such as fill or stroke
   *
   * @example
   * <Icon name="home" iconClassName="fill-current stroke-2" />
   */
  iconClassName?: string;
  /**
   * Stroke width of the icon
   *
   * @default 2
   */
  strokeWidth?: number;
  /**
   * Function called when the icon is clicked
   */
  onClick?: React.MouseEventHandler<HTMLElement>;
  /**
   * Inline styles for the wrapper element
   */
  style?: React.CSSProperties;
  /**
   * Data attribute for testing or identification
   */
  'data-testid'?: string;
  /**
   * ARIA label for accessibility (required if icon is interactive)
   */
  'aria-label'?: string;
  /**
   * Whether the icon is decorative (hidden from screen readers)
   *
   * @default true
   */
  'aria-hidden'?: boolean;
}

/**
 * Options for registering a new icon
 */
export interface RegisterIconOptions {
  /**
   * Name of the icon (must be unique)
   */
  name: IconName;
  /**
   * React component for the icon (should be a Lucide icon or compatible component)
   */
  component: LucideIcon;
}
