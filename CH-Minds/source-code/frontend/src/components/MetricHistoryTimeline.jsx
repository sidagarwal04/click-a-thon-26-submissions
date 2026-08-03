import { useEffect, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { getMetricHistory } from "@/api/client"

const METRICS = [
  { value: "all", label: "All metrics" },
  { value: "revenue", label: "Revenue" },
  { value: "fill_rate", label: "Fill rate" },
  { value: "render_rate", label: "Render rate" },
  { value: "ecpm", label: "eCPM" },
  { value: "ctr", label: "CTR" },
]
const REAL_METRICS = METRICS.filter((m) => m.value !== "all").map((m) => m.value)
const METRIC_LABEL = Object.fromEntries(METRICS.map((m) => [m.value, m.label]))

const GRID_COLUMNS = "2.5rem 1fr"

const LEGEND = [
  { color: "hsl(var(--primary))", label: "Normal" },
  { color: "#ef4444", label: "Anomalous (past that metric's threshold)" },
  { color: "#cbd5e1", label: "No baseline yet" },
]

function formatDay(iso) {
  return iso.slice(5)
}

function normalizeAllMetrics(results) {
  const dayCount = results[0]?.days?.length || 0
  const days = []
  for (let i = 0; i < dayCount; i++) {
    let best = null
    for (let mi = 0; mi < results.length; mi++) {
      const point = results[mi].days[i]
      if (!point || point.pct_deviation == null) continue
      if (best == null || Math.abs(point.pct_deviation) > Math.abs(best.pct_deviation)) {
        best = { ...point, metric: REAL_METRICS[mi], pct_threshold: results[mi].pct_threshold }
      }
    }
    days.push(best || { ...results[0].days[i], metric: null, pct_threshold: null })
  }
  return { days }
}

export default function MetricHistoryTimeline({ onInvestigate, investigating, fromDay, toDay, onDaysLoaded }) {
  const [metric, setMetric] = useState("all")
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hovered, setHovered] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setHovered(null)
    const fetchNormalized =
      metric === "all"
        ? Promise.all(REAL_METRICS.map((m) => getMetricHistory({ metric: m }))).then(normalizeAllMetrics)
        : getMetricHistory({ metric }).then((res) => ({
          days: res.days.map((d) => ({ ...d, metric, pct_threshold: res.pct_threshold })),
        }))

    fetchNormalized
      .then((res) => {
        setData(res)
        onDaysLoaded?.(res.days)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metric])

  const fullRange = data?.days || []
  const days = fullRange.filter((d) => (!fromDay || d.day >= fromDay) && (!toDay || d.day <= toDay))

  const maxAbsDeviation = Math.max(0.05, ...days.map((d) => Math.abs(d.pct_deviation ?? 0)))
  const labelStride = Math.max(1, Math.ceil(days.length / 7))

  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex flex-col gap-1">
          <CardTitle>Anomaly history</CardTitle>
          <CardDescription>Click any day - flagged or not - to investigate it.</CardDescription>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger className="h-8 w-32 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METRICS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!loading && !error && days.length === 0 && (
          <p className="text-sm text-muted-foreground">No days in this range.</p>
        )}
        {!loading && !error && days.length > 0 && (
          <div>
            <div className="grid gap-x-1.5" style={{ gridTemplateColumns: GRID_COLUMNS }}>
              <div className="flex h-44 flex-col justify-between py-0.5 text-right text-[9px] leading-none text-muted-foreground">
                <span>+{(maxAbsDeviation * 100).toFixed(0)}%</span>
                <span>0%</span>
                <span>-{(maxAbsDeviation * 100).toFixed(0)}%</span>
              </div>
              <div className="relative h-44 border-b border-l border-muted-foreground/40">
                <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-muted-foreground/30" />
                <div className="flex h-full items-stretch gap-px">
                  {days.map((d) => {
                    const pct = d.pct_deviation
                    const anomalous = pct != null && d.pct_threshold != null && Math.abs(pct) >= d.pct_threshold
                    const heightPct = pct == null ? 0 : Math.min(50, (Math.abs(pct) / maxAbsDeviation) * 50)
                    const isPositive = pct != null && pct >= 0
                    const color = anomalous ? "#ef4444" : pct == null ? "#cbd5e1" : "hsl(var(--primary))"
                    return (
                      <button
                        type="button"
                        key={d.day}
                        className="group relative flex-1 disabled:cursor-default"
                        disabled={pct == null || investigating}
                        onClick={() => onInvestigate({ metric: d.metric || metric, day: d.day })}
                        onMouseEnter={() => setHovered(d)}
                        onMouseLeave={() => setHovered((h) => (h?.day === d.day ? null : h))}
                      >
                        <span
                          className="absolute left-0 right-0 rounded-[1px] transition-opacity group-hover:opacity-70 group-disabled:opacity-100"
                          style={{
                            [isPositive ? "bottom" : "top"]: "50%",
                            height: `${heightPct}%`,
                            backgroundColor: color,
                            cursor: pct == null ? "default" : "pointer",
                          }}
                        />
                      </button>
                    )
                  })}
                </div>
              </div>

              <div />
              <div className="mt-1 flex text-[9px] leading-none text-muted-foreground">
                {days.map((d, i) => (
                  <span key={d.day} className="flex-1 whitespace-nowrap text-center">
                    {i % labelStride === 0 ? formatDay(d.day) : ""}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              {LEGEND.map((l) => (
                <span key={l.label} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ backgroundColor: l.color }} />
                  {l.label}
                </span>
              ))}
            </div>

            <p className="mt-2 h-4 text-xs text-muted-foreground">
              {hovered
                ? `${hovered.day}${metric === "all" && hovered.metric ? ` · ${METRIC_LABEL[hovered.metric]}` : ""}: ${hovered.pct_deviation != null
                  ? `${hovered.pct_deviation >= 0 ? "+" : ""}${(hovered.pct_deviation * 100).toFixed(1)}% vs baseline`
                  : "no baseline yet"
                }`
                : "Hover a bar for the exact number, click to investigate."}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
