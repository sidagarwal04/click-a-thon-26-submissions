import { useEffect, useMemo, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { getAllAnomaliesEver } from "@/api/client"

const METRICS = [
  { value: "all", label: "All metrics" },
  { value: "revenue", label: "Revenue" },
  { value: "fill_rate", label: "Fill rate" },
  { value: "render_rate", label: "Render rate" },
  { value: "ecpm", label: "eCPM" },
  { value: "ctr", label: "CTR" },
]

const METRIC_COLOR = {
  revenue: "hsl(var(--primary))",
  fill_rate: "#f59e0b",
  render_rate: "#10b981",
  ecpm: "#3b82f6",
  ctr: "#ef4444",
}
const METRIC_LABEL = Object.fromEntries(METRICS.map((m) => [m.value, m.label]))

function segmentLabel(segmentDims) {
  if (!segmentDims || !Object.keys(segmentDims).length) return "-"
  return Object.entries(segmentDims)
    .map(([k, v]) => `${k}=${v}`)
    .join(", ")
}

export default function AnomalyCountChart({ onInvestigate, allDays = [], fromDay, toDay }) {
  const [metric, setMetric] = useState("all")
  const [all, setAll] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)

  useEffect(() => {
    setLoading(true)
    getAllAnomaliesEver()
      .then(setAll)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    setSelectedDay(null)
  }, [fromDay, toDay])

  const filtered = useMemo(() => {
    if (!all) return []
    return metric === "all" ? all : all.filter((a) => a.metric === metric)
  }, [all, metric])

  const byDay = useMemo(() => {
    const map = new Map()
    for (const a of filtered) {
      if (!map.has(a.day)) map.set(a.day, { total: 0, byMetric: {}, items: [] })
      const entry = map.get(a.day)
      entry.total += 1
      entry.byMetric[a.metric] = (entry.byMetric[a.metric] || 0) + 1
      entry.items.push(a)
    }
    return map
  }, [filtered])

  const daysInRange = useMemo(
    () => allDays.filter((d) => (!fromDay || d >= fromDay) && (!toDay || d <= toDay)),
    [allDays, fromDay, toDay],
  )
  const maxCount = Math.max(1, ...daysInRange.map((d) => byDay.get(d)?.total || 0))
  const labelStride = Math.max(1, Math.ceil(daysInRange.length / 7))
  const selected = selectedDay ? byDay.get(selectedDay) : null

  const metricsInView = metric === "all" ? METRICS.slice(1).map((m) => m.value) : [metric]

  const visibleTotal = daysInRange.reduce((sum, d) => sum + (byDay.get(d)?.total || 0), 0)
  const metricTotals = useMemo(() => {
    const totals = {}
    for (const d of daysInRange) {
      const entry = byDay.get(d)
      if (!entry) continue
      for (const [m, c] of Object.entries(entry.byMetric)) totals[m] = (totals[m] || 0) + c
    }
    return totals
  }, [daysInRange, byDay])

  const ready = !loading && !error && allDays.length > 0

  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <CardTitle>Anomaly counts {ready && `(${visibleTotal})`}</CardTitle>
            <CardDescription>How many segment-level anomalies fired each day - breadth, not just deviation size.</CardDescription>
          </div>
          <Select value={metric} onValueChange={(v) => { setMetric(v); setSelectedDay(null) }}>
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
        {ready && (
          <div className="flex flex-wrap items-center gap-3">
            {metricsInView.map((m) => (
              <span key={m} className="flex items-center gap-1.5 text-[10px]">
                <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ backgroundColor: METRIC_COLOR[m] }} />
                <span className="text-muted-foreground">{METRIC_LABEL[m]}</span>
                <span className="font-semibold tabular-nums">{metricTotals[m] || 0}</span>
              </span>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!ready && !error && <p className="text-sm text-muted-foreground">Loading…</p>}
        {ready && daysInRange.length === 0 && (
          <p className="text-sm text-muted-foreground">No days in this range.</p>
        )}
        {ready && daysInRange.length > 0 && (
          <div>
            <div className="grid gap-x-1.5" style={{ gridTemplateColumns: "2rem 1fr" }}>
              <div className="flex h-40 flex-col justify-between py-0.5 text-right text-[9px] leading-none text-muted-foreground">
                <span>{maxCount}</span>
                <span>0</span>
              </div>
              <div className="relative h-40 border-b border-l border-muted-foreground/40">
                <div className="flex h-full items-end gap-px">
                  {daysInRange.map((d) => {
                    const entry = byDay.get(d)
                    const total = entry?.total || 0
                    const isSelected = selectedDay === d
                    return (
                      <button
                        type="button"
                        key={d}
                        className="group relative flex flex-1 flex-col-reverse overflow-hidden rounded-t-[1px] disabled:cursor-default"
                        style={{ height: "100%" }}
                        disabled={total === 0}
                        onClick={() => setSelectedDay(isSelected ? null : d)}
                        title={total > 0 ? `${d}: ${total} anomal${total === 1 ? "y" : "ies"}` : `${d}: none`}
                      >
                        {total === 0 ? (
                          <span className="h-px w-full bg-muted-foreground/30" />
                        ) : (
                          metricsInView
                            .filter((m) => entry.byMetric[m])
                            .map((m) => (
                              <span
                                key={m}
                                style={{
                                  height: `${(entry.byMetric[m] / maxCount) * 100}%`,
                                  backgroundColor: METRIC_COLOR[m],
                                  opacity: isSelected ? 1 : 0.85,
                                }}
                                className="w-full transition-opacity group-hover:opacity-100"
                              />
                            ))
                        )}
                        {isSelected && (
                          <span className="pointer-events-none absolute inset-x-0 top-0 h-0.5 bg-foreground" />
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div />
              <div className="mt-1 flex text-[9px] leading-none text-muted-foreground">
                {daysInRange.map((d, i) => (
                  <span key={d} className="flex-1 whitespace-nowrap text-center">
                    {i % labelStride === 0 ? d.slice(5) : ""}
                  </span>
                ))}
              </div>
            </div>

            {selected && (
              <div className="mt-3 border-t pt-3">
                <div className="mb-1.5 text-xs font-semibold">
                  {selectedDay} · {selected.total} anomal{selected.total === 1 ? "y" : "ies"}
                </div>
                <ul className="scroll-thin max-h-40 space-y-1 overflow-y-auto pr-1">
                  {selected.items.map((a) => (
                    <li key={a.id} className="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 text-xs hover:bg-muted/50">
                      <span className="truncate">
                        <span className="font-medium" style={{ color: METRIC_COLOR[a.metric] }}>
                          {METRIC_LABEL[a.metric] || a.metric}
                        </span>{" "}
                        · {segmentLabel(a.segment_dims)}{" "}
                        <span className={a.pct_deviation >= 0 ? "text-emerald-600" : "text-red-600"}>
                          ({a.pct_deviation >= 0 ? "+" : ""}
                          {(a.pct_deviation * 100).toFixed(1)}%)
                        </span>
                      </span>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 shrink-0 px-2 text-[10px]"
                        onClick={() => onInvestigate?.({ metric: a.metric, day: a.day, anomalyCandidateId: a.id })}
                      >
                        Investigate
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="mt-2 text-xs text-muted-foreground">
              {selected ? "Click the day again to close, or click a different day." : "Click a day to see which segments fired."}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
