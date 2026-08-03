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
import type { GlobalSeriesRow } from "@/lib/types";

interface Props {
  title: string;
  rows: GlobalSeriesRow[];
  loading?: boolean;
}

export function GlobalMetricChart({ title, rows, loading }: Props) {
  const data = rows.map((r) => ({
    bucket: r.bucket.slice(0, 10),
    actual: r.actual,
    expected: r.expected,
    z_score: r.z_score,
  }));

  return (
    <article className="flex min-h-[280px] flex-col border border-border bg-card/20">
      <header className="border-b border-border px-4 py-3">
        <h2>{title}</h2>
      </header>
      <div className="flex-1 p-3">
        {loading ? (
          <Skeleton className="h-[220px] w-full" />
        ) : rows.length === 0 ? (
          <p className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
            No data for this range. Adjust filters and Apply.
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
              <Line
                type="monotone"
                dataKey="actual"
                name="Actual"
                stroke="hsl(var(--chart-1))"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="expected"
                name="Expected"
                stroke="hsl(var(--chart-3))"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </article>
  );
}
