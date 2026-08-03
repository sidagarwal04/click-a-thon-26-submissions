import React, { useRef, useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
  Legend,
} from 'recharts';
import { IChartProps, IConfig, IEntry } from '../../components/Insight';
import { FloatingTooltip } from '../../common/FloatingTooltip';
import { Loader } from '../../common/Loader';
import { FunnelTooltip, FunnelTooltipPayloadItem } from './FunnelTooltip';

const META_KEYS = new Set([
  'fromtime',
  'totime',
  'date',
  'name',
  'value',
  'retentionRate',
  'baseTotal',
]);

const processData = (initialData: IEntry, stages: { label: string; key: string }[]) => {
  const data = stages.map((stage) => ({
    name: stage.label,
    value: Number(initialData[stage.label] ?? 0),
  }));

  const startValue = data[0]?.value || 1;
  return data.map((item, index) => ({
    ...item,
    retentionRate: index === 0 ? 100 : (item.value / startValue) * 100,
  }));
};

/**
 * One bar per dimension value, grouped by stage.
 * Height = that dimension's retention vs its own stage-1 absolute —
 * so side-by-side bars answer "which dim converts worst?"
 */
const processGroupedData = (rows: IEntry[], segments: IConfig[]) => {
  const baseByDim: Record<string, number> = {};
  const first = rows[0] ?? {};
  for (const segment of segments) {
    const key = segment.dataKey;
    if (!key) continue;
    baseByDim[key] = Number(first[key]) || 0;
  }

  const baseTotal = Object.values(baseByDim).reduce((sum, n) => sum + n, 0) || 1;

  return rows.map((row) => {
    const next: IEntry = {
      name: row.name ?? '',
      value: Number(row.value) || 0,
      baseTotal,
      retentionRate: ((Number(row.value) || 0) / baseTotal) * 100,
    };

    for (const segment of segments) {
      const key = segment.dataKey;
      if (!key) continue;
      const abs = Number(row[key]) || 0;
      const base = baseByDim[key] || 0;
      next[`__abs_${key}`] = abs;
      next[key] = base > 0 ? (abs / base) * 100 : 0;
    }

    for (const [key, value] of Object.entries(row)) {
      if (
        META_KEYS.has(key) ||
        key.startsWith('__abs_') ||
        segments.some((s) => s.dataKey === key)
      ) {
        continue;
      }
      next[key] = value;
    }

    return next;
  });
};

type HoverTip = {
  x: number;
  y: number;
  payload: FunnelTooltipPayloadItem[];
};

const Funnel: React.FC<IChartProps> = ({ data = [], chartsConfig = {}, loading, options }) => {
  const [containerWidth, setContainerWidth] = useState(400);
  const [hoverTip, setHoverTip] = useState<HoverTip | null>(null);
  const mouseRef = useRef({ x: 0, y: 0 });

  if (loading) {
    return <Loader className={'h-full w-full'} />;
  }

  const stages = chartsConfig?.funnel?.stages ?? [];
  const segments = chartsConfig?.funnel?.segments ?? [];
  const isGrouped = segments.length > 0;

  if (!stages.length || !data || data.length === 0) {
    return (
      <div className="flex h-full w-full flex-col">
        <div className="flex w-full grow items-center justify-center rounded-md">
          <p className="text-sm text-gray-500">No data</p>
        </div>
      </div>
    );
  }

  const chartData = isGrouped
    ? processGroupedData(data, segments)
    : processData(data[data.length - 1], stages);

  const barWidth = isGrouped
    ? Math.max(10, Math.floor(containerWidth / (chartData.length * segments.length + 2)))
    : Math.max(20, containerWidth / chartData.length);

  const CustomBar = (props: {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    index?: number;
  }) => {
    const { x = 0, y = 0, width = 0, height = 0, index = 0 } = props;

    if (index === 0) {
      return (
        <g>
          <rect x={x} y={y} width={width} height={height} fill="#3B82F6" />
        </g>
      );
    }

    const currentRetentionRate = Number(chartData[index]?.retentionRate) || 0;
    const previousRetentionRate = Number(chartData[index - 1]?.retentionRate) || 0;
    const fadeHeight =
      currentRetentionRate > 0 ? height * (previousRetentionRate / currentRetentionRate - 1) : 0;

    return (
      <g>
        <rect
          x={x}
          y={y - fadeHeight}
          width={width}
          height={fadeHeight}
          fill="#93C5FD"
          fillOpacity={0.6}
        />
        <rect x={x} y={y} width={width} height={height} fill="#3B82F6" />
      </g>
    );
  };

  return (
    <div
      className="h-full w-full pr-4 pt-4"
      onMouseMove={(event) => {
        mouseRef.current = { x: event.clientX, y: event.clientY };
        setHoverTip((prev) => (prev ? { ...prev, x: event.clientX, y: event.clientY } : prev));
      }}
      onMouseLeave={() => setHoverTip(null)}
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
        onResize={(width) => setContainerWidth(width)}
      >
        <ComposedChart
          data={chartData}
          barCategoryGap={isGrouped ? '28%' : '10%'}
          barGap={isGrouped ? 2 : 4}
          onMouseMove={(state) => {
            const payload = state?.activePayload as FunnelTooltipPayloadItem[] | undefined;
            if (!state?.isTooltipActive || !payload?.length) {
              setHoverTip(null);
              return;
            }
            setHoverTip({
              x: mouseRef.current.x,
              y: mouseRef.current.y,
              payload,
            });
          }}
          onMouseLeave={() => setHoverTip(null)}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: '#6B7280' }}
            tickFormatter={(value) => `${value}`}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: '#6B7280' }}
            tickFormatter={(value) => `${value}%`}
            domain={[0, 100]}
          />
          {isGrouped && <Legend verticalAlign="top" align="right" iconSize={7} iconType="circle" />}
          <Tooltip cursor={{ fill: 'rgba(148, 163, 184, 0.12)' }} content={() => null} />
          {isGrouped ? (
            segments
              .filter((segment): segment is typeof segment & { dataKey: string } =>
                Boolean(segment.dataKey),
              )
              .map((segment) => (
                <Bar
                  key={`funnel-seg-${segment.dataKey}`}
                  dataKey={segment.dataKey}
                  fill={segment.color}
                  maxBarSize={28}
                  radius={[3, 3, 0, 0]}
                />
              ))
          ) : (
            <Bar dataKey="retentionRate" shape={<CustomBar />} barSize={barWidth} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      {hoverTip && (
        <FloatingTooltip x={hoverTip.x} y={hoverTip.y} theme={options?.theme}>
          <FunnelTooltip payload={hoverTip.payload} />
        </FloatingTooltip>
      )}
    </div>
  );
};

export default Funnel;
