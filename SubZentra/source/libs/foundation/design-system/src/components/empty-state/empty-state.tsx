/**
 * EmptyState component
 * @module components/empty-state
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { EmptyStateActions } from './empty-state-actions';
import { EmptyStateDescription } from './empty-state-description';
import { EmptyStateTitle } from './empty-state-title';
import type { EmptyStateComponent, EmptyStateProps } from './types';
import { emptyStateDefaultTheme } from './types';

/**
 * EmptyState component
 *
 * A compound component for displaying empty states with an icon, title,
 * description, and action buttons.
 *
 * @example
 * <EmptyState icon={<SearchIcon />}>
 *   <EmptyState.Title>No results found</EmptyState.Title>
 *   <EmptyState.Description>
 *     Try adjusting your search or filters to find what you're looking for.
 *   </EmptyState.Description>
 *   <EmptyState.Actions>
 *     <Button>Clear filters</Button>
 *   </EmptyState.Actions>
 * </EmptyState>
 */
const EmptyStateRoot = React.forwardRef(function EmptyState<T extends React.ElementType = 'div'>(
  { component, className, children, ozid, size = 'md', compact, icon, ...rest }: EmptyStateProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('emptyState', emptyStateDefaultTheme);
  const Element = component ?? 'div';

  return (
    <Element
      ref={ref}
      className={theme.root({ className, size, compact })}
      data-ozid={ozid}
      role="status"
      {...rest}
    >
      {/* Icon slot */}
      {icon && (
        <Slot
          baseOzid={ozid}
          className={theme.icon?.({ size }) ?? ''}
          slotName="icon"
          slot={icon}
          component="div"
          aria-hidden="true"
        />
      )}

      {children}
    </Element>
  );
}) as unknown as EmptyStateComponent;

// Attach sub-components
EmptyStateRoot.displayName = 'EmptyState';
EmptyStateRoot.Title = EmptyStateTitle;
EmptyStateRoot.Description = EmptyStateDescription;
EmptyStateRoot.Actions = EmptyStateActions;

export const EmptyState = EmptyStateRoot;
