import React from "react";
import { cn } from "../utils/general.util";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string | React.ReactNode;
  className?: string;
  disabled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({ onClick, label, className, disabled, ...rest }) => {
  return (
    <button
      type="button"
      onClick={(e) => {
        if (!disabled && onClick) {
          onClick(e);
        }
      }}
      className={cn(
        "text-center rounded-md px-3 py-1.5 text-xs",
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
        className
      )}
      disabled={disabled}
      {...rest}
    >
      {label}
    </button>
  );
};
