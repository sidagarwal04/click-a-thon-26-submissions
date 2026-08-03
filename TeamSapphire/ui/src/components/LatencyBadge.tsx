import type { Investigation } from "@/types";

export function LatencyBadge({ investigation }: { investigation: Investigation }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg border border-border bg-card px-4 py-2.5 text-xs">
      <Stat label="query time" value={`${investigation.total_query_ms.toLocaleString(undefined, { maximumFractionDigits: 0 })} ms`} />
      <Stat label="rows read" value={investigation.total_rows_read.toLocaleString()} />
      <Stat label="queries" value={String(investigation.queries.length)} />
      <Stat label="runtime" value={`${investigation.runtime_seconds.toFixed(1)}s`} />
      {investigation.trace_url && (
        <a
          href={investigation.trace_url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto font-medium text-[#3987e5] hover:underline"
        >
          view trace ↗
        </a>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-semibold tabular-nums text-foreground">{value}</span>
      <span className="text-muted-foreground">{label}</span>
    </span>
  );
}
