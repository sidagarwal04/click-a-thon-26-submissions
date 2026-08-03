/**
 * ScrollArea component
 * @module components/scroll-area
 */
import React from 'react';

import { ScrollArea as ScrollAreaPrimitive } from '@base-ui/react/scroll-area';

import { useTheme } from '../../theme';
import { cn } from '../../utils/cn';
import type { ScrollAreaComponent, ScrollAreaProps } from './types';
import { scrollAreaDefaultTheme } from './types';

/**
 * ScrollArea component
 *
 * A container with custom scrollbars for overflow content.
 *
 * @example
 * <ScrollArea height={300}>
 *   <div className="p-4">
 *     {longContent}
 *   </div>
 * </ScrollArea>
 *
 * @example
 * // Horizontal scroll
 * <ScrollArea orientation="horizontal" height={100}>
 *   <div className="flex gap-4">
 *     {items.map(...)}
 *   </div>
 * </ScrollArea>
 *
 * @example
 * // Always visible scrollbars
 * <ScrollArea type="always" maxHeight={400}>
 *   Content...
 * </ScrollArea>
 */
export const ScrollArea = React.forwardRef(function ScrollArea<T extends React.ElementType = 'div'>(
  {
    component: _component,
    className,
    ozid,
    orientation = 'vertical',
    type = 'hover',
    height,
    maxHeight,
    viewportRef,
    children,
    ...rest
  }: ScrollAreaProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('scrollArea', scrollAreaDefaultTheme);

  const style: React.CSSProperties = {
    height: typeof height === 'number' ? `${height}px` : height,
    maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight,
  };

  const showVertical = orientation === 'vertical' || orientation === 'both';
  const showHorizontal = orientation === 'horizontal' || orientation === 'both';

  return (
    <ScrollAreaPrimitive.Root
      ref={ref as React.Ref<HTMLDivElement>}
      className={cn(theme.root?.({ orientation, type }), type === 'hover' && 'group', className)}
      data-ozid={ozid}
      style={style}
      {...rest}
    >
      <ScrollAreaPrimitive.Viewport
        ref={viewportRef}
        className={theme.viewport?.({ orientation }) ?? ''}
        data-ozid={ozid ? `${ozid}__viewport` : undefined}
      >
        {children}
      </ScrollAreaPrimitive.Viewport>

      {/* Vertical scrollbar */}
      {showVertical && (
        <ScrollAreaPrimitive.Scrollbar
          orientation="vertical"
          className={theme.scrollbarVertical?.({ type }) ?? ''}
        >
          <ScrollAreaPrimitive.Thumb className={theme.thumb?.({}) ?? ''} />
        </ScrollAreaPrimitive.Scrollbar>
      )}

      {/* Horizontal scrollbar */}
      {showHorizontal && (
        <ScrollAreaPrimitive.Scrollbar
          orientation="horizontal"
          className={theme.scrollbarHorizontal?.({ type }) ?? ''}
        >
          <ScrollAreaPrimitive.Thumb className={theme.thumb?.({}) ?? ''} />
        </ScrollAreaPrimitive.Scrollbar>
      )}

      {/* Corner for when both scrollbars are visible */}
      {orientation === 'both' && (
        <ScrollAreaPrimitive.Corner className={theme.corner?.({}) ?? ''} />
      )}
    </ScrollAreaPrimitive.Root>
  );
}) as ScrollAreaComponent;

ScrollArea.displayName = 'ScrollArea';
