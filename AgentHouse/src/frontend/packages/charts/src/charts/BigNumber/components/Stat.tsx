import React from "react";
import { cn, valueFormatter } from "../../../utils/general.util";
import { Change } from "./Change";

export type IStatProps = {
  label?: string;
  value: number;
  change: number;
  changeType: string;
  interval: string;
  align?: string;
  className?: string;
  font?: "small" | "medium" | "large";
  unit?: string;
  /** When provided, replaces the period chip and "vs {interval}" with this custom label. */
  periodLabel?: string;
  /** 4-line layout: current window description e.g. "April so far · Apr 1–4" or "March · complete". */
  currentWindowLabel?: string;
};

export const Stat: React.FC<IStatProps> = ({
  label,
  value,
  change,
  changeType,
  interval,
  align = "center",
  className = "",
  font = "large",
  unit = "",
  periodLabel,
  currentWindowLabel,
}) => {
  const valueFontSize = {
    small: "text-xl",
    medium: "text-2xl",
    large: "text-3xl",
  };

  const changeFontSize = {
    small: "text-xs",
    medium: "text-xs",
    large: "text-sm",
  };

  if (currentWindowLabel) {
    // 3-line layout: value / ↑↓ X% vs {interval} / {currentWindowLabel}
    // Outer container positions the block per `align` prop (center | start | end).
    // Inner block always left-aligns its lines relative to each other.
    return (
      <div
        className={cn(
          `h-full p-3 flex flex-col justify-center ${
            align === "center" ? "items-center" : align === "start" ? "items-start" : "items-end"
          }`,
          className
        )}
      >
        <div className="flex flex-col gap-0.5 items-start">
          <p className={`${valueFontSize[font]} font-semibold text-gray-700 leading-none`}>
            {valueFormatter(value)}{unit ? ` ${unit}` : ""}
          </p>
          <div className="flex items-center gap-1 mt-0.5">
            <Change change={change} changeType={changeType} className={changeFontSize[font]} />
            <span className={`${changeFontSize[font]} font-light text-gray-500`}>vs {interval}</span>
          </div>
          <p className="text-xs text-gray-400 leading-none mt-0.5">{currentWindowLabel}</p>
        </div>
      </div>
    );
  }

  if (periodLabel) {
    // Custom layout: [value  delta] on one line, period label below
    return (
      <div
        className={cn(
          `h-full p-3 flex flex-col gap-0.5 ${
            align === "center" ? "items-center" : align === "start" ? "items-start" : "items-end"
          } justify-center`,
          className
        )}
      >
        <div className="flex items-end gap-2">
          <p className={`${valueFontSize[font]} font-medium text-gray-700 leading-none`}>
            {valueFormatter(value)}{unit ? ` ${unit}` : ""}
          </p>
          <Change change={change} changeType={changeType} className={`${changeFontSize[font]} mb-[1px]`} />
        </div>
        <p className="text-xs font-normal text-gray-500 leading-snug">{periodLabel}</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        `h-full p-3 flex flex-col gap-1 ${
          align === "center" ? "items-center" : align === "start" ? "items-start" : "items-end"
        } justify-center`,
        className
      )}
    >
      <div className="flex flex-col items-start text-gray-900 gap-y-1">
        <p className="inline-block px-1.5 text-[10px] border border-gray-300 font-light rounded-md text-gray-600">
          {label}
        </p>
        <div className="flex items-end gap-1">
          <p className={`${valueFontSize[font]} font-medium text-gray-700`}>{valueFormatter(value)}</p>
          <p className={`font-medium text-gray-600 mb-[1.5px]`}>{unit}</p>
        </div>
      </div>
      <div className="flex justify-center items-center gap-1">
        <Change change={change} changeType={changeType} className={changeFontSize[font]} />
        <span className={`${changeFontSize[font]} font-light`}>vs {interval}</span>
      </div>
    </div>
  );
};
