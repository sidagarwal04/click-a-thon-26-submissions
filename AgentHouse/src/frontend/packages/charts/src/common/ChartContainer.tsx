import { useState } from "react";
import { Button } from "./Button";
import { TfiInfoAlt } from "react-icons/tfi";
import { MenuItem, PopUpMenu } from "./PopUpMenu";
import { PiDotsThreeVerticalBold } from "react-icons/pi";

interface IChartContainerProps {
  title: string;
  description?: string;
  className?: string;
  actions?: MenuItem[];
  onClick?: () => void;
  onCheck?: (...args: any) => void;
  children: React.ReactNode;
}

export const ChartContainer = ({
  title,
  description,
  className,
  actions,
  onClick,
  onCheck,
  children,
}: IChartContainerProps) => {
  const [showDescription, setShowDescription] = useState<boolean>(false);
  return (
    <div
      className={`w-full flex flex-col justify-between relative border border-gray-300 bg-white rounded-xl ${className}`}
    >
      <div id="chart-header" className="pt-2.5 pb-1.5 px-4">
        <div className="flex flex-wrap gap-2 justify-between items-center">
          <p
            className={`text-sm text-left text-nowrap overflow-x-auto no-scrollbar max-w-[80%] ${
              onClick ? "hover:underline" : ""
            } cursor-pointer`}
            onClick={onClick}
          >
            {title}
          </p>
          <div className="flex-grow flex items-center justify-end gap-x-2">
            {description && (
              <Button
                className="cursor-pointer !w-auto !p-0 !m-0 shadow-transparent rounded-none"
                onClick={() => setShowDescription(!showDescription)}
                label={<TfiInfoAlt size={14} />}
              />
            )}
            {actions && actions.length > 0 && (
              <PopUpMenu label={<PiDotsThreeVerticalBold size={16} aria-hidden="true" />} menuItems={actions} />
            )}
            {onCheck && (
              <input
                type="checkbox"
                className="rounded-lg p-3 cursor-pointer"
                onChange={(e) => onCheck(e.target.checked)}
              />
            )}
          </div>
        </div>
      </div>

      <div id="chart-body" className="flex flex-col flex-grow cursor-pointer relative overflow-auto">
        <div
          className={`${
            showDescription ? `max-h-full border-b` : `max-h-0`
          } transition-all duration-500 absolute overflow-hidden left-0 top-0 bg-white w-full z-10`}
        >
          <p className="text-xxs h-full text-gray-500 font-sans text-left px-3 py-1">{description}</p>
        </div>

        {children}
      </div>
    </div>
  );
};
