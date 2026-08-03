import { AlertTriangle, Clock, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RcaTrigger } from "@/lib/types";

interface Props {
  trigger: RcaTrigger;
  status: string;
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(2)}%`;
}

function fmtWindow(w: { start: string; end: string }) {
  return `${w.start.slice(0, 16).replace("T", " ")} → ${w.end.slice(0, 16).replace("T", " ")}`;
}

export function TriggerCard({ trigger, status }: Props) {
  const hasSignal = trigger.actual !== undefined && trigger.expected !== undefined;
  const delta = hasSignal ? trigger.actual! - trigger.expected! : undefined;

  return (
    <article className="border border-border bg-card/20">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden />
          <h2>What triggered this RCA</h2>
        </div>
        <Badge variant={status === "localized" ? "default" : "secondary"}>{status}</Badge>
      </header>
      <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Alert</p>
          <p className="mt-1 text-sm font-medium text-foreground">{trigger.alert_title}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{trigger.alert_body}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Metric</p>
          <p className="mt-1 font-mono text-sm text-foreground">{trigger.metric_id}</p>
          {trigger.dimension_hint && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              hint: {trigger.dimension_hint}
            </p>
          )}
        </div>
        <div>
          <p className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            <Clock className="h-3 w-3" aria-hidden />
            Window
          </p>
          <p className="mt-1 font-mono text-xs text-foreground">{fmtWindow(trigger.window)}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {trigger.hours !== undefined ? `${trigger.hours} hours` : "—"}
          </p>
        </div>
        <div>
          <p className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            <Zap className="h-3 w-3" aria-hidden />
            Signal
          </p>
          {hasSignal ? (
            <>
              <p className="mt-1 font-mono text-sm tabular-nums text-foreground">
                {fmtPct(trigger.actual!)} vs {fmtPct(trigger.expected!)}
              </p>
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                Δ {delta! >= 0 ? "+" : ""}
                {(delta! * 100).toFixed(2)}pp
                {trigger.peak_abs_z !== undefined && ` · peak |z| ${trigger.peak_abs_z.toFixed(1)}`}
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              No finding — alert did not reproduce against current data.
            </p>
          )}
        </div>
      </div>
    </article>
  );
}
