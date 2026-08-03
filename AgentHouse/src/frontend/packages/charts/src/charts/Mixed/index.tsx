import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Legend,
  Tooltip,
  Bar,
  Line,
  Area,
} from "recharts";
import { valueFormatter } from "../../utils/general.util";
import { CustomTooltip } from "../../common/CustomTooltip";
import { IChartProps } from "../../components/Insight";
import { Loader } from "../../common/Loader";
import { CompactTooltip, ICustomTooltipProps } from "../../common/CompactTooltip";

const MixedChart: React.FC<IChartProps> = ({
  data = [],
  loading,
  height = "100%",
  width = "100%",
  fontSize = 12,
  chartsConfig = {},
  options = {},
}) => {
  const { compact = false } = options;

  if (loading) {
    return <Loader className={"h-full w-full"} />;
  }

  if (!chartsConfig || !data || data.length === 0) {
    return (
      <div className="w-full h-full flex flex-col">
        <div className="flex w-full grow justify-center items-center rounded-md">
          <p className="text-gray-500 text-sm">No data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col justify-between h-full">
      <ResponsiveContainer width={width} height={height} minHeight={24}>
        <ComposedChart data={data}>
          {!compact && (
            <>
              <CartesianGrid stroke="#e7e7e7" vertical={false} horizontal={true} strokeDasharray="5 5" />
              <XAxis dataKey={"date"} axisLine={false} tickLine={false} fontFamily="sans-serif" fontSize={fontSize} />
              <YAxis
                axisLine={false}
                tickLine={false}
                fontFamily="sans-serif"
                tickFormatter={valueFormatter}
                fontSize={fontSize}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                fontFamily="sans-serif"
                yAxisId="right"
                orientation="right"
                tickFormatter={valueFormatter}
                fontSize={fontSize}
              />
              <Legend verticalAlign="top" align="right" iconSize={7} iconType="circle" />
            </>
          )}

          <Tooltip
            content={(props: ICustomTooltipProps) =>
              compact ? <CompactTooltip {...props} /> : <CustomTooltip {...props} />
            }
          />

          {chartsConfig.bars?.map((x, idx) => (
            <Bar
              key={`bar-${idx}`}
              dataKey={x.dataKey}
              barSize={30}
              fill={x.color}
              stackId={x.stackId ?? `stack-${idx}`}
              {...((idx === chartsConfig.bars.length - 1 || !x.stackId) && {
                radius: [5, 5, 0, 0],
              })}
            />
          ))}

          {chartsConfig.lines?.map((x, idx) => (
            <Line
              key={`line-${idx}`}
              type="monotone"
              dataKey={x.dataKey}
              stroke={x.color}
              dot={false}
              strokeWidth={2}
              yAxisId={x.yAxisId}
            />
          ))}

          {chartsConfig.areas?.map((x, idx) => {
            const colorId = `area-gradient-${idx}`;
            return (
              <React.Fragment key={`area-${idx}`}>
                <defs>
                  <linearGradient id={colorId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={x.color} stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#FFFFFF" stopOpacity={1} />
                  </linearGradient>
                </defs>
                <Area
                  fill={`url(#${colorId})`}
                  type="monotone"
                  dataKey={x.dataKey}
                  stroke={x.color}
                  dot={false}
                  strokeWidth={2}
                  yAxisId={x.yAxisId}
                />
              </React.Fragment>
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default MixedChart;
