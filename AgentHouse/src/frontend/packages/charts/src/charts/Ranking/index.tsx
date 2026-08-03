import { useState } from "react";
import { Loader } from "../../common/Loader";
import { FloatingTooltip } from "../../common/FloatingTooltip";
import { IChartProps } from "../../components/Insight";
import { formatString, valueFormatter } from "../../utils/general.util";
import { RankingTooltip } from "./RankingTooltip";

const Ranking: React.FC<IChartProps> = ({ chartsConfig, data, loading, options }) => {
  const [tooltip, setTooltip] = useState<{
    show: boolean;
    x: number;
    y: number;
    segment: string;
    value: number;
    percentage: number;
    rank: number;
  } | null>(null);

  if (loading) return <Loader className="min-h-32 h-full" />;

  if (!chartsConfig || !data || data.length === 0)
    return (
      <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">
        Please select a breakdown
      </div>
    );

  const sortedData = [...data].sort((a, b) => Number(b.value) - Number(a.value));
  const total = sortedData.reduce((acc, curr) => acc + Number(curr.value), 0);
  const maxPercentage = Math.max(...sortedData.map((d) => Number(d.percentage)));

  const handleMouseEnter = (
    e: React.MouseEvent,
    segment: string,
    value: number,
    percentage: number,
    rank: number,
  ) => {
    setTooltip({
      show: true,
      x: e.clientX,
      y: e.clientY,
      segment,
      value,
      percentage,
      rank,
    });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    setTooltip((prev) =>
      prev
        ? {
            ...prev,
            x: e.clientX,
            y: e.clientY,
          }
        : null,
    );
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  return (
    <div className="w-full flex flex-col relative">
      <p className="px-3 pt-2 pb-1 border-b border-gray-300 text-sm text-gray-500 flex-shrink-0">
        {formatString(chartsConfig?.ranking?.dimension)}
      </p>
      <div className="flex flex-col text-sm">
        {sortedData.map((d, index) => {
          const normalizedWidth = (Number(d.percentage) / maxPercentage) * 100;
          const barWidth = Math.max(5, normalizedWidth);

          return (
            <div
              key={index}
              className="flex px-3 py-2 flex-row justify-between items-center border-b border-gray-300 gap-2 hover:bg-white/5 cursor-pointer"
              onMouseEnter={(e) =>
                handleMouseEnter(e, String(d.segment), Number(d.value), Number(d.percentage), index + 1)
              }
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
            >
              <div className="text-sm text-gray-600 w-1/6 truncate">{d.segment}</div>
              <div className="flex flex-row items-center w-3/6">
                <div
                  className="rounded-md bg-blue-400 h-3 transition-all duration-300"
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <div className="text-sm text-gray-600 w-1/6 text-right">{valueFormatter(Number(d.value))}</div>
              <div className="text-xs text-gray-500 w-1/6 text-right">{Number(d.percentage).toFixed(2)}%</div>
            </div>
          );
        })}
      </div>

      <div className="flex-shrink-0 px-3 py-2 text-sm flex justify-between items-center gap-2 font-semibold text-gray-700 border-b border-gray-300">
        <div className="w-4/6">Total</div>
        <div className="w-1/6 text-right">{valueFormatter(total)}</div>
        <div className="w-1/6 text-right">100%</div>
      </div>

      {tooltip?.show ? (
        <FloatingTooltip x={tooltip.x} y={tooltip.y} theme={options?.theme}>
          <RankingTooltip
            segment={tooltip.segment}
            value={tooltip.value}
            percentage={tooltip.percentage}
            rank={tooltip.rank}
            dimension={formatString(chartsConfig?.ranking?.dimension)}
          />
        </FloatingTooltip>
      ) : null}
    </div>
  );
};

export default Ranking;
