import { valueFormatter } from "../../utils/general.util";

interface PivotTooltipProps {
  rowValue: string;
  colValue: string;
  value: number;
  rowLabel?: string;
  colLabel?: string;
}

export const PivotTooltip: React.FC<PivotTooltipProps> = ({
  rowValue,
  colValue,
  value,
  rowLabel = "Segment",
  colLabel = "Category",
}) => {
  return (
    <div className="da-tooltip min-w-40 bg-white rounded-lg shadow-lg border border-gray-300 text-sm overflow-hidden">
      {/* Top section with blue indicator and value */}
      <div className="flex items-center p-3 border-b border-gray-300">
        <div className="w-1 h-8 bg-blue-500 rounded mr-3"></div>
        <span className="text-lg font-bold">{valueFormatter(value)}</span>
      </div>

      {/* Middle section with column value */}
      <div className="p-3 border-b border-gray-300">
        <div className="text-gray-800">{colValue}</div>
        <div className="text-gray-500 text-xs">{colLabel}</div>
      </div>

      {/* Bottom section with row value */}
      <div className="p-3">
        <div className="text-gray-800">{rowValue}</div>
        <div className="text-gray-500 text-xs">{rowLabel}</div>
      </div>
    </div>
  );
};
