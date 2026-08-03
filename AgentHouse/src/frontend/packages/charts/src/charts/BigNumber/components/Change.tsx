import React from "react";
import { IoMdArrowDown, IoMdArrowUp } from "react-icons/io";
import { cn } from "../../../utils/general.util";

interface ChangeProps {
  change: number;
  changeType: string;
  className?: string;
  iconSize?: number;
}

export const Change: React.FC<ChangeProps> = ({ change, changeType, className, iconSize = 12 }) => {
  return (
    <span
      className={cn(
        `${changeType === "negative" ? "text-rose-600" : "text-green-700"} text-sm flex items-center gap-0.5`,
        className
      )}
    >
      {changeType === "positive" ? (
        <IoMdArrowUp color="green" size={iconSize} />
      ) : (
        <IoMdArrowDown color="red" size={iconSize} />
      )}
      {`${change}%`}
    </span>
  );
};
