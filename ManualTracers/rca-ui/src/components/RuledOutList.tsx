import { XCircle } from "lucide-react";
import type { RcaRuledOut } from "@/lib/types";

interface Props {
  items: RcaRuledOut[];
  candidatesTested: number;
}

export function RuledOutList({ items, candidatesTested }: Props) {
  return (
    <article className="border border-border bg-card/20">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <XCircle className="h-4 w-4 text-muted-foreground" aria-hidden />
        <h2>Checked and ruled out</h2>
      </header>
      <div className="px-4 py-3">
        <p className="mb-3 text-sm text-muted-foreground">
          {candidatesTested} depth-1 candidates scanned. Notable near-misses that failed holdout:
        </p>
        <ul className="space-y-3">
          {items.map((item) => (
            <li
              key={item.segment}
              className="rounded-sm border border-border bg-muted/30 px-3 py-2"
            >
              <p className="font-mono text-sm text-foreground">{item.segment}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.reason}</p>
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}
