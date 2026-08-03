import { valueFormatter } from "../../utils/general.util";

interface RankingTooltipProps {
  segment: string;
  value: number;
  percentage: number;
  rank: number;
  dimension?: any;
}

export const RankingTooltip: React.FC<RankingTooltipProps> = ({
  segment,
  value,
  percentage,
  rank,
  dimension = "Dimension",
}) => {
  return (
    <div className="da-tooltip min-w-40 bg-white rounded-lg shadow-lg border border-gray-300 text-sm overflow-hidden">
      {/* Top section with blue indicator and value */}
      <div className="flex items-center p-3 border-b border-gray-300">
        <div className="w-1 h-8 bg-blue-500 rounded mr-3"></div>
        <span className="text-lg font-bold">{valueFormatter(value)}</span>
      </div>

      {/* Middle section with segment */}
      <div className="p-3 border-b border-gray-300">
        <div className="text-gray-800">{segment}</div>
        <div className="text-gray-500 text-xs">{String(dimension || "Dimension")}</div>
      </div>

      {/* Bottom section with rank and percentage */}
      <div className="p-3">
        <div className="text-gray-800">
          #{rank} • {percentage.toFixed(2)}%
        </div>
        <div className="text-gray-500 text-xs">Rank & Percentage</div>
      </div>
    </div>
  );
};
