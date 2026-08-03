import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { SegmentSeriesRow } from "@/lib/types";

const CHART_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
];

interface Props {
  rows: SegmentSeriesRow[];
  loading?: boolean;
}

function pivot(rows: SegmentSeriesRow[]) {
  const buckets = [...new Set(rows.map((r) => r.bucket))].sort();
  const series = [...new Set(rows.map((r) => r.os_version))];
  return buckets.map((bucket) => {
    const point: Record<string, string | number> = { bucket: bucket.slice(0, 10) };
    for (const s of series) {
      const row = rows.find((r) => r.bucket === bucket && r.os_version === s);
      point[s] = row ? row.fill_rate : undefined;
    }
    return point;
  });
}

export function SegmentTrendChart({ rows, loading }: Props) {
  const data = pivot(rows);
  const series = [...new Set(rows.map((r) => r.os_version))];

  return (
    <article className="flex min-h-[280px] flex-col border border-border bg-card/20">
      <header className="border-b border-border px-4 py-3">
        <h2>Fill rate by OS (segment drill-down)</h2>
      </header>
      <div className="flex-1 p-3">
        {loading ? (
          <Skeleton className="h-[220px] w-full" />
        ) : rows.length === 0 ? (
          <p className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
            No data for this range.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="bucket"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={48}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "var(--radius)",
                  fontSize: 12,
                }}
                formatter={(value) =>
                  value != null ? `${(Number(value) * 100).toFixed(2)}%` : ""
                }
              />
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
              {series.map((s, i) => (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </article>
  );
}
