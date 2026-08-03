/**
 * MultiSelect component
 * @module components/multi-select
 *
 * A dropdown that allows selecting multiple options.
 * Uses CheckboxGroup internally for selection state management.
 */
import React, { useCallback, useMemo, useState } from 'react';

import { Popover as PopoverPrimitive } from '@base-ui/react/popover';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { cn } from '../../utils/cn';
import { Checkbox } from '../checkbox';
import { CheckboxGroupContext } from '../checkbox-group/checkbox-group.context';
import { ScrollArea } from '../scroll-area';
import type { MultiSelectProps } from './types';
import { multiSelectDefaultTheme } from './types';

/**
 * MultiSelect component
 *
 * A dropdown allowing multiple selections with search and counter badge.
 *
 * @example
 * const [selected, setSelected] = useState<string[]>([]);
 *
 * <MultiSelect
 *   options={[
 *     { value: 'react', label: 'React' },
 *     { value: 'vue', label: 'Vue' },
 *     { value: 'angular', label: 'Angular' },
 *   ]}
 *   value={selected}
 *   onValueChange={setSelected}
 *   placeholder="Select frameworks..."
 *   searchable
 *   showCounter
 * />
 */
export const MultiSelect = React.forwardRef<HTMLDivElement, MultiSelectProps>(function MultiSelect(
  {
    ozid,
    size = 'md',
    feedback = 'default',
    disabled,
    readOnly,
    showCounter = true,
    value: controlledValue,
    defaultValue = [],
    onValueChange: controlledOnValueChange,
    options,
    placeholder = 'Select...',
    start,
    end,
    searchPlaceholder = 'Search...',
    searchable = false,
    maxHeight = 300,
    closeOnSelect = false,
    label,
    className,
    ...rest
  },
  ref,
) {
  const theme = useTheme('multiSelect', multiSelectDefaultTheme);

  // Internal state for uncontrolled mode
  const [internalValue, setInternalValue] = useState<string[]>(defaultValue);
  const [searchQuery, setSearchQuery] = useState('');
  const [open, setOpen] = useState(false);

  // Determine if controlled or uncontrolled
  const isControlled = controlledValue !== undefined;
  const value = isControlled ? controlledValue : internalValue;

  const onValueChange = useCallback(
    (newValue: string[]) => {
      if (!isControlled) {
        setInternalValue(newValue);
      }
      controlledOnValueChange?.(newValue);
    },
    [isControlled, controlledOnValueChange],
  );

  // Filter options by search
  const filteredOptions = useMemo(() => {
    if (!searchQuery) return options;
    const query = searchQuery.toLowerCase();
    return options.filter((option) => option.label.toLowerCase().includes(query));
  }, [options, searchQuery]);

  // Get display text
  const displayText = useMemo(() => {
    if (value.length === 0) return null;
    const selectedLabels = options
      .filter((opt) => value.includes(opt.value))
      .map((opt) => opt.label);
    return selectedLabels.join(', ');
  }, [value, options]);

  // Handle item selection
  const handleItemToggle = (optionValue: string) => {
    const newValue = value.includes(optionValue)
      ? value.filter((v) => v !== optionValue)
      : [...value, optionValue];
    onValueChange(newValue);
    if (closeOnSelect) {
      setOpen(false);
    }
  };

  // Context value for CheckboxGroup integration
  const checkboxGroupContext = useMemo(
    () => ({
      value,
      onValueChange,
      disabled,
      size: size as 'sm' | 'md' | 'lg',
      orientation: 'vertical' as const,
    }),
    [value, onValueChange, disabled, size],
  );

  // Map size for checkbox
  const checkboxSize = size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md';

  return (
    <CheckboxGroupContext.Provider value={checkboxGroupContext}>
      <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
        {/* rest first: caller-supplied lang, aria and data attributes reach the
            root, but never at the cost of the props managed here. */}
        <div
          {...rest}
          ref={ref}
          className={
            theme.root?.({ className, size, feedback, disabled, readOnly, showCounter }) ??
            className
          }
          data-ozid={ozid}
        >
          <PopoverPrimitive.Trigger
            className={theme.trigger?.({ size, feedback, disabled }) ?? ''}
            disabled={disabled || readOnly}
            aria-label={label}
            data-ozid={ozid ? `${ozid}__trigger` : undefined}
          >
            {/* Start slot */}
            {start && (
              <Slot
                baseOzid={ozid}
                slotName="start"
                slot={start}
                component="span"
                aria-hidden="true"
              />
            )}

            {/* Content */}
            <span className={theme.triggerContent?.({}) ?? ''}>
              {displayText ? (
                <span className="truncate">{displayText}</span>
              ) : (
                <Slot
                  baseOzid={ozid}
                  className={theme.placeholder?.({}) ?? ''}
                  slotName="placeholder"
                  slot={placeholder}
                  component="span"
                >
                  {placeholder}
                </Slot>
              )}
            </span>

            {/* Counter badge */}
            {showCounter && value.length > 0 && (
              <span className={theme.counter?.({ size }) ?? ''}>{value.length}</span>
            )}

            {/* End slot / chevron */}
            {end ? (
              <Slot baseOzid={ozid} slotName="end" slot={end} component="span" aria-hidden="true" />
            ) : (
              <Icon
                name="chevron_down"
                className={cn(theme.icon?.({}) ?? '', open && 'rotate-180')}
              />
            )}
          </PopoverPrimitive.Trigger>

          <PopoverPrimitive.Portal>
            <PopoverPrimitive.Positioner sideOffset={4}>
              <PopoverPrimitive.Popup
                className={theme.content?.({}) ?? ''}
                data-ozid={ozid ? `${ozid}__content` : undefined}
              >
                {/* Search */}
                {searchable && (
                  <div className={theme.search?.({ size }) ?? ''}>
                    <Icon name="search" className="h-4 w-4 shrink-0 opacity-50 mr-2" />
                    <input
                      type="text"
                      placeholder={searchPlaceholder}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className={theme.searchInput?.({ size }) ?? ''}
                      data-ozid={ozid ? `${ozid}__search` : undefined}
                    />
                  </div>
                )}

                {/* Options list */}
                <ScrollArea maxHeight={maxHeight}>
                  <div
                    className={theme.list?.({}) ?? ''}
                    role="listbox"
                    aria-multiselectable="true"
                  >
                    {filteredOptions.length === 0 ? (
                      <div className={theme.empty?.({}) ?? ''}>No options found</div>
                    ) : (
                      filteredOptions.map((option) => {
                        const isSelected = value.includes(option.value);
                        const isDisabled = option.disabled || disabled;

                        return (
                          <div
                            key={option.value}
                            role="option"
                            aria-selected={isSelected}
                            aria-disabled={isDisabled}
                            data-disabled={isDisabled || undefined}
                            className={theme.item?.({ size }) ?? ''}
                            onClick={() => !isDisabled && handleItemToggle(option.value)}
                            data-ozid={ozid ? `${ozid}__item-${option.value}` : undefined}
                          >
                            <span className={theme.itemIndicator?.({}) ?? ''}>
                              <Checkbox
                                checked={isSelected}
                                disabled={isDisabled}
                                size={checkboxSize}
                                tabIndex={-1}
                                aria-hidden="true"
                              />
                            </span>
                            {option.label}
                          </div>
                        );
                      })
                    )}
                  </div>
                </ScrollArea>
              </PopoverPrimitive.Popup>
            </PopoverPrimitive.Positioner>
          </PopoverPrimitive.Portal>
        </div>
      </PopoverPrimitive.Root>
    </CheckboxGroupContext.Provider>
  );
});

MultiSelect.displayName = 'MultiSelect';
