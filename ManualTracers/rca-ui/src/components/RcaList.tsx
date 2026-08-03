import { FileSearch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RcaReportSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  reports: RcaReportSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function fmtDate(iso: string) {
  return iso.slice(0, 16).replace("T", " ");
}

export function RcaList({ reports, selectedId, onSelect }: Props) {
  return (
    <aside className="border-r border-border bg-card/30">
      <header className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <FileSearch className="h-4 w-4 text-muted-foreground" aria-hidden />
          <h2 className="text-sm font-medium text-foreground">Recent RCAs</h2>
        </div>
      </header>
      <ul className="divide-y divide-border">
        {reports.map((r) => (
          <li key={r.id}>
            <button
              type="button"
              onClick={() => onSelect(r.id)}
              className={cn(
                "w-full px-4 py-3 text-left transition-colors hover:bg-muted/40",
                selectedId === r.id && "bg-primary/10 border-l-2 border-l-primary",
              )}
            >
              <p className="text-sm font-medium leading-snug text-foreground">{r.title}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className="text-[10px] font-normal">
                  {r.metric_id}
                </Badge>
                <Badge variant="secondary" className="text-[10px] font-normal">
                  {r.status}
                </Badge>
                {r.peak_abs_z !== undefined && (
                  <span className="font-mono text-[10px] text-muted-foreground">
                    |z| {r.peak_abs_z.toFixed(1)}
                  </span>
                )}
              </div>
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                {fmtDate(r.created_at)}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
