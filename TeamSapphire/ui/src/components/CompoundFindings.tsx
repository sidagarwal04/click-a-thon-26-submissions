import type { CompoundFinding } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function CompoundFindings({ findings }: { findings: CompoundFinding[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Compound segments</CardTitle>
        <p className="text-xs text-muted-foreground">
          Two-dimension combinations that broke together even though neither dimension looked
          abnormal on its own — invisible to a scan that only ever checks one dimension at a time.
        </p>
      </CardHeader>
      <CardContent>
        {findings.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No compound anomalies found beyond what the single-dimension events above already
            explain — that is itself a checked-and-cleared finding, not an empty state.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-left">Day</TableHead>
                <TableHead className="text-left">Combination</TableHead>
                <TableHead className="text-left">Combined drop</TableHead>
                <TableHead className="text-left">First dimension alone</TableHead>
                <TableHead className="text-left">Second dimension alone</TableHead>
                <TableHead className="text-left">Requests</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {findings.map((f) => (
                <TableRow key={`${f.day}-${f.dim_a}-${f.value_a}-${f.dim_b}-${f.value_b}`}>
                  <TableCell className="text-left tabular-nums text-muted-foreground">{f.day}</TableCell>
                  <TableCell className="text-left font-medium text-foreground">
                    {f.dim_a}={f.value_a} + {f.dim_b}={f.value_b}
                  </TableCell>
                  <TableCell className="text-left tabular-nums text-muted-foreground">
                    {(f.pct_change * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell className="text-left tabular-nums text-muted-foreground">
                    {f.value_a}: {(f.parent_a_pct * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell className="text-left tabular-nums text-muted-foreground">
                    {f.value_b}: {(f.parent_b_pct * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell className="text-left tabular-nums text-muted-foreground">
                    {f.requests.toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
