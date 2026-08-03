export interface FunnelTooltipPayloadItem {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string | number;
  payload?: Record<string, string | number>;
}

export interface FunnelTooltipProps {
  active?: boolean;
  payload?: FunnelTooltipPayloadItem[];
}

/** Compact funnel hover card — stage header + one line per dimension. */
export const FunnelTooltip: React.FC<FunnelTooltipProps> = ({ active = true, payload }) => {
  if (!active || !payload?.length) {
    return null;
  }

  const data = payload[0]?.payload ?? {};
  const retentionRate = Number(data.retentionRate) || 0;
  const total = Number(data.value) || 0;
  const isGrouped = Object.keys(data).some((key) => key.startsWith("__abs_"));

  return (
    <div className="da-tooltip bg-white text-gray-900 rounded-md shadow-lg border border-gray-200 px-3 py-2 text-xs min-w-[148px] max-w-[220px]">
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <span className="font-semibold text-sm truncate">{data.name}</span>
        <span className="font-bold text-sm shrink-0">{retentionRate.toFixed(1)}%</span>
      </div>
      {!isGrouped && (
        <div className="text-gray-500">{total.toLocaleString()} customers</div>
      )}
      {isGrouped && (
        <div className="space-y-1">
          {payload.map((item) => {
            const key = String(item.dataKey ?? item.name ?? "");
            const abs = Number(data[`__abs_${key}`] ?? 0);
            const conversion = Number(item.value) || 0;
            return (
              <div key={key} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span
                    className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: item.color ?? "#3B82F6" }}
                  />
                  <span className="truncate text-gray-900">{key}</span>
                </div>
                <span className="shrink-0 text-gray-700 tabular-nums">
                  {conversion.toFixed(0)}% · {abs.toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
