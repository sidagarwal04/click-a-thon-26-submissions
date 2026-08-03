/**
 * VisuallyHidden component - Content visible only to screen readers
 * @module primitives/visually-hidden
 */

import React from 'react';

import { visuallyHiddenClasses } from '../../utils/a11y';
import { cn } from '../../utils/cn';

export interface VisuallyHiddenProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Content to hide visually but keep accessible */
  children: React.ReactNode;
  /** Additional className */
  className?: string;
  /** Render as a different element */
  component?: React.ElementType;
}

/**
 * VisuallyHidden component
 *
 * Renders content that is visually hidden but still accessible to screen readers.
 * Useful for providing additional context to assistive technologies.
 *
 * @example
 * // Hide loading text visually
 * <Button loading>
 *   <VisuallyHidden>Loading, please wait</VisuallyHidden>
 *   <Spinner />
 * </Button>
 *
 * @example
 * // Provide context for icon-only buttons
 * <IconButton>
 *   <SearchIcon />
 *   <VisuallyHidden>Search</VisuallyHidden>
 * </IconButton>
 */
export const VisuallyHidden = React.forwardRef<HTMLSpanElement, VisuallyHiddenProps>(
  function VisuallyHidden({ children, className, component: Component = 'span', ...props }, ref) {
    return (
      <Component ref={ref} className={cn(visuallyHiddenClasses, className)} {...props}>
        {children}
      </Component>
    );
  },
);

VisuallyHidden.displayName = 'VisuallyHidden';
