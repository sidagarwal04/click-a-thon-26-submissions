import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { ContributionRow } from "@/lib/types";

interface Props {
  rows: ContributionRow[];
  loading?: boolean;
}

export function ContributionChart({ rows, loading }: Props) {
  const data = rows.map((r) => ({
    name: r.segment.replace("=", "\n="),
    contribution: r.contribution,
  }));

  return (
    <article className="flex min-h-[280px] flex-col border border-border bg-card/20">
      <header className="border-b border-border px-4 py-3">
        <h2>Contribution by segment</h2>
      </header>
      <div className="flex-1 p-3">
        {loading ? (
          <Skeleton className="h-[220px] w-full" />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 9 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "var(--radius)",
                  fontSize: 12,
                }}
              />
              <Bar dataKey="contribution" fill="hsl(var(--chart-1))" radius={[0, 2, 2, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </article>
  );
}
