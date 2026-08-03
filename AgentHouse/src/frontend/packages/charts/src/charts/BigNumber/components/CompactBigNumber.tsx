import React, { ReactNode } from "react";
import { cn } from "../../../utils/general.util";

interface CompactBigNumberProps {
  number: string | ReactNode;
  label: string;
  numberFont?: string;
  numberAlign?: string;
  hideLabel?: boolean;
  className?: string;
}

export const CompactBigNumber: React.FC<CompactBigNumberProps> = ({
  number,
  label,
  hideLabel,
  numberFont,
  className,
}) => {
  return (
    <div className={cn("h-full flex flex-col justify-center items-center", className)}>
      <div className={cn("text-base text-gray-900", numberFont)}>{number}</div>
      {!hideLabel && label && <div className={cn("text-xs text-gray-600 text-center")}>{label}</div>}
    </div>
  );
};
