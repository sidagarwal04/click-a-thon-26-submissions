import React from "react";
import { PopupWrapper } from "./PopupWrapper";
import { Button } from "./Button";
import { cn } from "../utils/general.util";

export interface MenuItem {
  name?: string;
  onClick?: () => void;
  disabled?: boolean;
  component?: React.ReactNode;
}

interface MenuProps {
  menuItems: MenuItem[];
  close?: () => void;
}

const Menu: React.FC<MenuProps> = ({ menuItems, close }) => {
  return (
    <div className="min-w-52 rounded-md overflow-hidden bg-white shadow-sm border border-gray-300 z-40">
      {menuItems.map((item, index) =>
        item.component ? (
          <React.Fragment key={index}>{item.component}</React.Fragment>
        ) : (
          <Button
            key={index}
            label={item.name || ""}
            onClick={() => {
              item.onClick?.();
              close?.();
            }}
            disabled={item.disabled}
            className={cn(
              "w-full px-4 py-2 text-xxs text-left rounded-none",
              index < menuItems.length - 1 ? "border-b" : "",
              item.disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:bg-gray-100 hover:text-gray-800"
            )}
          />
        )
      )}
    </div>
  );
};

interface PopUpMenuProps {
  menuItems: MenuItem[];
  label: string | React.ReactNode;
}

export const PopUpMenu: React.FC<PopUpMenuProps> = ({ menuItems, label }) => {
  return (
    <PopupWrapper trigger={<Button className="w-auto px-0 py-0" label={label} />}>
      {(props) => <Menu menuItems={menuItems} close={props.close} />}
    </PopupWrapper>
  );
};
