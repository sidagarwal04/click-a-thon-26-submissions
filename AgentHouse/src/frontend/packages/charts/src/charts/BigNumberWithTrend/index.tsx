import React from "react";
import { Stat } from "../BigNumber/components/Stat";
import { Loader } from "../../common/Loader";
import { getChange, getSum, valueFormatter } from "../../utils/general.util";
import { TimeGrainAPIKey } from "../../constants/date.constant";
import { ComposedChart, CartesianGrid, Tooltip, ResponsiveContainer, Area, XAxis, YAxis } from "recharts";
import { IChartProps } from "../../components/Insight";
import { CustomTooltip } from "../../common/CustomTooltip";
import { CompactTooltip, ICustomTooltipProps } from "../../common/CompactTooltip";
import { getCurrLabel } from "../BigNumber/utils/bigNumber.util";

const BigNumberWithTrend: React.FC<IChartProps> = ({
  data,
  loading,
  timeGrain,
  height = "100%",
  width = "100%",
  chartsConfig = {},
}) => {
  if (loading) {
    return <Loader className="h-full" />;
  }

  if (!timeGrain || !chartsConfig?.stat || data?.length === 0) {
    return (
      <div className="w-full h-full p-2">
        <div className="flex w-full h-full justify-center items-center rounded-md">
          <p className="text-gray-500">No data</p>
        </div>
      </div>
    );
  }

  const metricLabel = chartsConfig.stat.dataKey;
  const metricChange = getChange(data, [metricLabel]);
  const currentValue = getSum(data[data.length - 1], [metricLabel]);

  return (
    <div className="h-full flex rounded-lg">
      {/* Header Section */}
      <div className="min-w-20 p-4">
        <Stat
          label={getCurrLabel(data, timeGrain)}
          value={currentValue}
          change={metricChange}
          changeType={metricChange > 0 ? "positive" : "negative"}
          interval={`last ${TimeGrainAPIKey[timeGrain]}`}
          align="start"
          className="justify-end p-0"
          font="medium"
          unit={chartsConfig?.stat?.unit}
        />
      </div>

      {/* Chart Section */}
      <div className="h-full flex-1 min-h-0 pr-4 pb-2 pt-4">
        <ResponsiveContainer width={width} height={height}>
          <ComposedChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
            <defs>
              <linearGradient id="areaGradientPositive" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10B981" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#FFFFFF" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="areaGradientNegative" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#FFFFFF" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} horizontal={false} />
            <Tooltip
              content={(props: ICustomTooltipProps) => <CompactTooltip {...props} />}
              cursor={{ stroke: "#3B82F6", strokeWidth: 1, strokeDasharray: "3 3" }}
            />
            {chartsConfig.areas?.map((area, index) => (
              <Area
                key={`area-${index}`}
                type="monotone"
                dataKey={area.dataKey}
                stroke={metricChange >= 0 ? "#10B981" : "#EF4444"}
                strokeWidth={2}
                fill={metricChange >= 0 ? "url(#areaGradientPositive)" : "url(#areaGradientNegative)"}
                dot={false}
                activeDot={{
                  r: 4,
                  fill: metricChange >= 0 ? "#10B981" : "#EF4444",
                  stroke: "#ffffff",
                  strokeWidth: 2,
                }}
                yAxisId={area.yAxisId}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default BigNumberWithTrend;
