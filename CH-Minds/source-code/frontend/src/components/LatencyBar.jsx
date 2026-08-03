import { useState } from "react"
import { ChevronDown, ChevronRight, Timer } from "lucide-react"

const CH_COLOR = "hsl(var(--primary))"
const LLM_COLOR = "#f59e0b"
const OTHER_COLOR = "hsl(var(--muted-foreground) / 0.35)"

const STAGE_LABELS = {
  day_coverage: "Check day completeness",
  compute_thresholds: "Compute dynamic thresholds",
  overall_deviation: "Top-line deviation",
  factor_decomposition: "Revenue factor decomposition",
  segment_ranking: "Rank segments (9 dimensions)",
  refine_segment: "Multi-dimension refinement",
  narrate: "LLM narration",
}

function ms(v) {
  if (v == null) return "-"
  return v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`
}

export default function LatencyBar({ timings }) {
  const [open, setOpen] = useState(false)
  if (!timings || !timings.total_ms) return null

  const { total_ms, clickhouse_ms, llm_ms, other_ms, stages } = timings
  const pct = (v) => (total_ms > 0 ? (v / total_ms) * 100 : 0)

  const stageRows = Object.entries(stages || {}).sort((a, b) => b[1].ms - a[1].ms)

  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
          <Timer className="h-3.5 w-3.5" />
          End-to-end latency
        </div>
        <div className="text-xs font-medium tabular-nums">{ms(total_ms)}</div>
      </div>

      <div className="mt-2 flex h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div style={{ width: `${pct(clickhouse_ms)}%`, backgroundColor: CH_COLOR }} title={`ClickHouse ${ms(clickhouse_ms)}`} />
        <div style={{ width: `${pct(llm_ms)}%`, backgroundColor: LLM_COLOR }} title={`LLM ${ms(llm_ms)}`} />
        <div style={{ width: `${pct(other_ms)}%`, backgroundColor: OTHER_COLOR }} title={`Other ${ms(other_ms)}`} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: CH_COLOR }} />
          ClickHouse analysis <span className="font-medium tabular-nums">{ms(clickhouse_ms)}</span>
          <span className="text-muted-foreground">({pct(clickhouse_ms).toFixed(0)}%)</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: LLM_COLOR }} />
          LLM narration <span className="font-medium tabular-nums">{ms(llm_ms)}</span>
          <span className="text-muted-foreground">({pct(llm_ms).toFixed(0)}%)</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: OTHER_COLOR }} />
          App + write <span className="font-medium tabular-nums">{ms(other_ms)}</span>
        </span>
      </div>

      {stageRows.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Per-stage breakdown
          </button>
          {open && (
            <table className="mt-1.5 w-full text-[11px]">
              <tbody>
                {stageRows.map(([name, s]) => (
                  <tr key={name} className="border-t border-border/50">
                    <td className="py-1 pr-2">{STAGE_LABELS[name] || name}</td>
                    <td className="py-1 pr-2 text-right tabular-nums text-muted-foreground">
                      {s.calls > 1 ? `${s.calls} calls` : ""}
                    </td>
                    <td className="w-14 py-1 text-right font-medium tabular-nums">{ms(s.ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
