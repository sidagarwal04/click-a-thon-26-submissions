import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import type { RcaCandidate } from "@/lib/types";

interface Props {
  rows: RcaCandidate[];
  loading?: boolean;
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(2)}%`;
}

export function CandidateTable({ rows, loading }: Props) {
  return (
    <article className="border border-border bg-card/20">
      <header className="border-b border-border px-4 py-3">
        <h2>Supporting data — candidate ranking</h2>
      </header>
      <div className="overflow-x-auto p-2">
        {loading ? (
          <Skeleton className="mx-2 h-40 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Segment</TableHead>
                <TableHead className="text-right">Actual</TableHead>
                <TableHead className="text-right">Expected</TableHead>
                <TableHead className="text-right">Peak |z|</TableHead>
                <TableHead className="text-right">Contribution</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={`${r.dim_name}-${r.dim_value}`}>
                  <TableCell className="font-mono text-sm text-foreground">
                    {i === 0 && (
                      <span className="mr-2 rounded bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary">
                        top
                      </span>
                    )}
                    {r.dim_name}={r.dim_value}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-foreground">
                    {fmtPct(r.avg_actual)}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                    {fmtPct(r.avg_expected)}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-foreground">
                    {r.peak_abs_z.toFixed(1)}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-foreground">
                    {r.contribution.toFixed(0)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </article>
  );
}
