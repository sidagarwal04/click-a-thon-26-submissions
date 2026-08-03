import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loader } from "../../common/Loader";
import { IChartProps } from "../../components/Insight";
import { valueFormatter } from "../../utils/general.util";
import { CustomTooltip } from "../../common/CustomTooltip";
import { ICustomTooltipProps } from "../../common/CompactTooltip";

const XMR: React.FC<IChartProps> = ({ chartsConfig, data, loading, height = "100%", width = "100%" }) => {
  if (loading) return <Loader className="min-h-32 h-full" />;

  if (!chartsConfig || !data || data.length === 0)
    return <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">No data</div>;

  return (
    <div className="flex flex-col justify-between h-full">
      <ResponsiveContainer width={width} height={height} minHeight={24}>
        <ComposedChart data={data}>
          <CartesianGrid stroke="#e7e7e7" vertical={false} horizontal={true} strokeDasharray="5 5" />
          <XAxis dataKey={"date"} axisLine={false} tickLine={false} fontFamily="sans-serif" fontSize={12} />
          <YAxis
            axisLine={false}
            tickLine={false}
            fontFamily="sans-serif"
            tickFormatter={valueFormatter}
            fontSize={12}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            fontFamily="sans-serif"
            yAxisId="right"
            orientation="right"
            tickFormatter={valueFormatter}
            fontSize={12}
          />
          <Legend verticalAlign="top" align="right" iconSize={7} iconType="circle" />

          <Tooltip content={(props: ICustomTooltipProps) => <CustomTooltip {...props} />} />

          {chartsConfig.lines?.map((x, idx) => (
            <Line
              key={`line-${idx}`}
              type="monotone"
              dataKey={x.dataKey}
              stroke={x.color}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

export default XMR;
