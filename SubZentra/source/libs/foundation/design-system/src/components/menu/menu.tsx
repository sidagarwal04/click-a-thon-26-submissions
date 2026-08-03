/**
 * Menu component
 * @module components/menu
 */
import { useMemo } from 'react';
import * as React from 'react';

import { Menu as MenuPrimitive } from '@base-ui/react/menu';

import { Icon } from '@open-zentra/foundation-icons';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { Checkbox } from '../checkbox';
import { MenuContext } from './menu.context';
import type {
  MenuCheckboxItemProps,
  MenuComponent,
  MenuContentProps,
  MenuContextValue,
  MenuGroupLabelProps,
  MenuGroupProps,
  MenuItemProps,
  MenuRadioGroupProps,
  MenuRadioItemProps,
  MenuSeparatorProps,
  MenuSubContentProps,
  MenuSubProps,
  MenuSubTriggerProps,
  MenuTriggerProps,
} from './types';
import { menuDefaultTheme } from './types';

// ============================================================================
// Menu Root
// ============================================================================

const MenuRoot: MenuComponent = ({
  size = 'md',
  open,
  defaultOpen,
  onOpenChange,
  onClear,
  children,
}) => {
  const contextValue: MenuContextValue = useMemo(
    () => ({
      size,
      onClear,
    }),
    [size, onClear],
  );

  return (
    <MenuContext.Provider value={contextValue}>
      <MenuPrimitive.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        {children}
      </MenuPrimitive.Root>
    </MenuContext.Provider>
  );
};

// ============================================================================
// Menu Trigger
// ============================================================================

const MenuTrigger: React.FC<MenuTriggerProps> = ({ children, disabled, ozid }) => (
  <MenuPrimitive.Trigger disabled={disabled} data-ozid={ozid} data-slot="trigger">
    {children}
  </MenuPrimitive.Trigger>
);
MenuTrigger.displayName = 'Menu.Trigger';

// ============================================================================
// Menu Content
// ============================================================================

const MenuContent = React.forwardRef<HTMLDivElement, MenuContentProps>(function MenuContent(
  {
    children,
    sideOffset = 4,
    alignOffset,
    side = 'bottom',
    align = 'start',
    ozid,
    className,
    ...rest
  },
  ref,
) {
  const theme = useTheme('menu', menuDefaultTheme);
  const { size } = useMenuContext();

  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner
        sideOffset={sideOffset}
        alignOffset={alignOffset}
        side={side}
        align={align}
        className={theme.positioner?.({}) ?? ''}
      >
        {/* rest first: caller-supplied lang, aria and data attributes reach the
            root, but never at the cost of the props managed here. */}
        <MenuPrimitive.Popup
          {...rest}
          ref={ref}
          // size is a declared Menu variant, so the popup has to offer the
          // theme a chance to style it even though the built-in classes for it
          // live on the item slot.
          className={theme.popup?.({ className, size }) ?? className}
          data-ozid={ozid}
          data-slot="content"
        >
          {children}
        </MenuPrimitive.Popup>
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  );
});
MenuContent.displayName = 'Menu.Content';

// ============================================================================
// Menu Item
// ============================================================================

const MenuItem: React.FC<MenuItemProps> = ({
  children,
  disabled,
  onSelect,
  closeOnSelect = true,
  start,
  end,
  ozid,
}) => {
  const theme = useTheme('menu', menuDefaultTheme);
  const { size } = useMenuContext();

  return (
    <MenuPrimitive.Item
      disabled={disabled}
      closeOnClick={closeOnSelect}
      onClick={onSelect}
      className={theme.item?.({ size }) ?? ''}
      data-ozid={ozid}
      data-slot="item"
    >
      {start && (
        <Slot
          baseOzid={ozid}
          className={theme.itemStart?.({ size }) ?? ''}
          slotName="start"
          slot={start}
          component="span"
          aria-hidden="true"
        />
      )}
      {children}
      {end && (
        <Slot
          baseOzid={ozid}
          className={theme.itemEnd?.({}) ?? ''}
          slotName="end"
          slot={end}
          component="span"
        />
      )}
    </MenuPrimitive.Item>
  );
};
MenuItem.displayName = 'Menu.Item';

// ============================================================================
// Menu Checkbox Item
// ============================================================================

const MenuCheckboxItem: React.FC<MenuCheckboxItemProps> = ({
  children,
  checked,
  onCheckedChange,
  disabled,
  closeOnSelect = false,
  ozid,
}) => {
  const theme = useTheme('menu', menuDefaultTheme);
  const { size } = useMenuContext();

  const handleClick = () => {
    onCheckedChange?.(!checked);
  };

  return (
    <MenuPrimitive.Item
      disabled={disabled}
      closeOnClick={closeOnSelect}
      onClick={handleClick}
      className={theme.checkboxItem?.({ size }) ?? ''}
      data-ozid={ozid}
      data-slot="checkboxItem"
      data-checked={checked || undefined}
    >
      <span className={theme.checkboxIndicator?.({ size }) ?? ''}>
        <Checkbox
          checked={checked}
          disabled={disabled}
          size={size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md'}
          tabIndex={-1}
        />
      </span>
      {children}
    </MenuPrimitive.Item>
  );
};
MenuCheckboxItem.displayName = 'Menu.CheckboxItem';

// ============================================================================
// Menu Radio Group
// ============================================================================

const MenuRadioGroupContext = React.createContext<{
  value?: string;
  onValueChange?: (value: string) => void;
} | null>(null);

const MenuRadioGroup: React.FC<MenuRadioGroupProps> = ({
  children,
  value,
  onValueChange,
  ozid,
}) => {
  const contextValue = useMemo(() => ({ value, onValueChange }), [value, onValueChange]);

  return (
    <MenuRadioGroupContext.Provider value={contextValue}>
      <MenuPrimitive.RadioGroup
        value={value}
        onValueChange={onValueChange}
        data-ozid={ozid}
        data-slot="radioGroup"
      >
        {children}
      </MenuPrimitive.RadioGroup>
    </MenuRadioGroupContext.Provider>
  );
};
MenuRadioGroup.displayName = 'Menu.RadioGroup';

// ============================================================================
// Menu Radio Item
// ============================================================================

const MenuRadioItem: React.FC<MenuRadioItemProps> = ({
  children,
  value,
  disabled,
  closeOnSelect = false,
  ozid,
}) => {
  const theme = useTheme('menu', menuDefaultTheme);
  const { size } = useMenuContext();
  const radioContext = React.useContext(MenuRadioGroupContext);
  const isChecked = radioContext?.value === value;

  return (
    <MenuPrimitive.RadioItem
      value={value}
      disabled={disabled}
      closeOnClick={closeOnSelect}
      className={theme.radioItem?.({ size }) ?? ''}
      data-ozid={ozid}
      data-slot="radioItem"
      data-checked={isChecked || undefined}
    >
      <span className={theme.radioIndicator?.({ size }) ?? ''}>
        {isChecked && <span className="h-2 w-2 rounded-full bg-current" />}
      </span>
      {children}
    </MenuPrimitive.RadioItem>
  );
};
MenuRadioItem.displayName = 'Menu.RadioItem';

// ============================================================================
// Menu Group
// ============================================================================

const MenuGroup: React.FC<MenuGroupProps> = ({ children, ozid }) => {
  const theme = useTheme('menu', menuDefaultTheme);

  return (
    <MenuPrimitive.Group className={theme.group?.({}) ?? ''} data-ozid={ozid} data-slot="group">
      {children}
    </MenuPrimitive.Group>
  );
};
MenuGroup.displayName = 'Menu.Group';

// ============================================================================
// Menu Group Label
// ============================================================================

const MenuGroupLabel: React.FC<MenuGroupLabelProps> = ({ children, ozid }) => {
  const theme = useTheme('menu', menuDefaultTheme);

  return (
    <MenuPrimitive.GroupLabel
      className={theme.groupLabel?.({}) ?? ''}
      data-ozid={ozid}
      data-slot="groupLabel"
    >
      {children}
    </MenuPrimitive.GroupLabel>
  );
};
MenuGroupLabel.displayName = 'Menu.GroupLabel';

// ============================================================================
// Menu Separator
// ============================================================================

const MenuSeparator: React.FC<MenuSeparatorProps> = ({ ozid }) => {
  const theme = useTheme('menu', menuDefaultTheme);

  return (
    <MenuPrimitive.Separator
      className={theme.separator?.({}) ?? ''}
      data-ozid={ozid}
      data-slot="separator"
    />
  );
};
MenuSeparator.displayName = 'Menu.Separator';

// ============================================================================
// Menu Sub
// ============================================================================

const MenuSub: React.FC<MenuSubProps> = ({ children, open, defaultOpen, onOpenChange, ozid }) => {
  return (
    <MenuPrimitive.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
      {children}
    </MenuPrimitive.Root>
  );
};
MenuSub.displayName = 'Menu.Sub';

// ============================================================================
// Menu Sub Trigger
// ============================================================================

const MenuSubTrigger: React.FC<MenuSubTriggerProps> = ({ children, disabled, start, ozid }) => {
  const theme = useTheme('menu', menuDefaultTheme);
  const { size } = useMenuContext();

  return (
    <MenuPrimitive.SubmenuTrigger
      disabled={disabled}
      className={theme.subTrigger?.({ size }) ?? ''}
      data-ozid={ozid}
      data-slot="subTrigger"
    >
      {start && (
        <Slot
          baseOzid={ozid}
          className={theme.itemStart?.({ size }) ?? ''}
          slotName="start"
          slot={start}
          component="span"
          aria-hidden="true"
        />
      )}
      {children}
      <Icon name="chevron_right" className={theme.subTriggerIcon?.({ size }) ?? ''} />
    </MenuPrimitive.SubmenuTrigger>
  );
};
MenuSubTrigger.displayName = 'Menu.SubTrigger';

// ============================================================================
// Menu Sub Content
// ============================================================================

const MenuSubContent: React.FC<MenuSubContentProps> = ({ children, ozid }) => {
  const theme = useTheme('menu', menuDefaultTheme);

  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner sideOffset={2} className={theme.positioner?.({}) ?? ''}>
        <MenuPrimitive.Popup
          className={theme.subContent?.({}) ?? ''}
          data-ozid={ozid}
          data-slot="subContent"
        >
          {children}
        </MenuPrimitive.Popup>
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  );
};
MenuSubContent.displayName = 'Menu.SubContent';

// ============================================================================
// Helper hook for context
// ============================================================================

function useMenuContext() {
  const context = React.useContext(MenuContext);
  if (!context) {
    return { size: 'md' as const };
  }
  return context;
}

// ============================================================================
// Attach sub-components
// ============================================================================

MenuRoot.displayName = 'Menu';
MenuRoot.Trigger = MenuTrigger;
MenuRoot.Content = MenuContent;
MenuRoot.Item = MenuItem;
MenuRoot.CheckboxItem = MenuCheckboxItem;
MenuRoot.RadioGroup = MenuRadioGroup;
MenuRoot.RadioItem = MenuRadioItem;
MenuRoot.Group = MenuGroup;
MenuRoot.GroupLabel = MenuGroupLabel;
MenuRoot.Separator = MenuSeparator;
MenuRoot.Sub = MenuSub;
MenuRoot.SubTrigger = MenuSubTrigger;
MenuRoot.SubContent = MenuSubContent;

export const Menu = MenuRoot;
