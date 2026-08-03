import type { RuledOutEntry, Verdict } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const VERDICT_COLOR: Record<Verdict, string> = {
  uniform: "#0ca30c",
  inconclusive: "#fab219",
  responsible: "#d03b3b", // should not appear here, but kept for completeness
  not_applicable: "#898781", // grey: not a weak signal, an undefined question
};

export function RuledOutList({ ruledOut }: { ruledOut: RuledOutEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Checked and ruled out</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-left">Dimension</TableHead>
              <TableHead className="text-left">Verdict</TableHead>
              <TableHead className="text-left">Top value</TableHead>
              <TableHead className="text-left">Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ruledOut.map((v) => (
              <TableRow key={v.dim_name}>
                <TableCell className="align-top text-left font-medium text-foreground">{v.dim_name}</TableCell>
                <TableCell className="align-top text-left">
                  <span
                    className="inline-block whitespace-nowrap rounded-full border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                    style={{
                      color: VERDICT_COLOR[v.verdict],
                      borderColor: `${VERDICT_COLOR[v.verdict]}66`,
                      backgroundColor: `${VERDICT_COLOR[v.verdict]}1f`,
                    }}
                  >
                    {v.verdict.replace("_", " ")}
                  </span>
                </TableCell>
                <TableCell className="align-top text-left text-muted-foreground">{v.top_value}</TableCell>
                {/* The TableCell primitive sets whitespace-nowrap, so a long
                    reason overflows into a horizontal scroll instead of
                    wrapping — and the half a reader needs is the half off
                    screen. Override it and give the column room. */}
                <TableCell className="w-1/2 whitespace-normal align-top text-left leading-snug text-muted-foreground">
                  {v.reason}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
