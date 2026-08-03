/**
 * Foundation Icons Library
 *
 * A thin, extensible wrapper over lucide-react icons with Tailwind-driven
 * sizing and styling. This library provides a consistent icon API across
 * the application.
 *
 * @packageDocumentation
 */

// Initialize icon registry by importing the icons
// This ensures all icons are registered when the library is imported
import './registry';

// Export the Icon component (used by design-system)
export { Icon } from './icon';
export { ICON_NAMES } from './registry/registry';
export type { IconName } from './registry/registry';
export type { IconProps } from './types';
