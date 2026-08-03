import { useEffect, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { getDayHourScan } from "@/api/client"

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

function formatHour(hod) {
  return `${String(hod).padStart(2, "0")}:00`
}

function mergeAllMetrics(resultsByMetric) {
  const hourCount = Math.max(0, ...Object.values(resultsByMetric).map((r) => r?.length ?? 0))
  const merged = []
  for (let i = 0; i < hourCount; i++) {
    const flags = []
    for (const [metric, hours] of Object.entries(resultsByMetric)) {
      const seg = hours?.[i]?.responsible_segment
      if (seg) flags.push({ metric, responsible_segment: seg })
    }
    flags.sort((a, b) => Math.abs(b.responsible_segment.pct_deviation) - Math.abs(a.responsible_segment.pct_deviation))
    const anyHour = Object.values(resultsByMetric).find((r) => r?.[i])?.[i]
    merged.push({ hour: anyHour.hour, hod: anyHour.hod, flags })
  }
  return merged
}

function flagsFor(h, metric) {
  if (metric === "all") return h.flags
  return h.responsible_segment ? [{ metric, responsible_segment: h.responsible_segment }] : []
}

function blockBackground(flags, metric) {
  if (flags.length === 0) return "hsl(var(--muted))"
  if (metric !== "all") return "#ef4444"
  if (flags.length === 1) return METRIC_COLOR[flags[0].metric]
  const stops = flags.map(
    (f, i) => `${METRIC_COLOR[f.metric]} ${(i / flags.length) * 100}% ${((i + 1) / flags.length) * 100}%`
  )
  return `linear-gradient(to right, ${stops.join(", ")})`
}

export default function HourScanStrip({ day, onInvestigate }) {
  const [metric, setMetric] = useState("all")
  const [hours, setHours] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSelected(null)
    const targets = metric === "all" ? METRICS.slice(1).map((m) => m.value) : [metric]
    Promise.all(targets.map((m) => getDayHourScan({ metric: m, day }).then((res) => [m, res.hours])))
      .then((pairs) => {
        const byMetric = Object.fromEntries(pairs)
        setHours(metric === "all" ? mergeAllMetrics(byMetric) : byMetric[metric])
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [metric, day])

  const flaggedCount = hours?.filter((h) => flagsFor(h, metric).length > 0).length ?? 0

  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <CardTitle>Hour breakdown {hours && `(${flaggedCount}/24 flagged)`}</CardTitle>
            <CardDescription>Which hours of {day} had a responsible segment - not just the whole-day number.</CardDescription>
          </div>
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger className="h-8 w-36 text-xs">
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
        {loading && <p className="text-sm text-muted-foreground">Scanning 24 hours…</p>}
        {!loading && !error && hours && (
          <div>
            <div className="flex gap-0.5">
              {hours.map((h) => {
                const flags = flagsFor(h, metric)
                const flagged = flags.length > 0
                const background = blockBackground(flags, metric)
                const isSelected = selected?.hour === h.hour
                const title = flagged
                  ? `${formatHour(h.hod)}: ${flags
                    .map(
                      (f) =>
                        `${metric === "all" ? `${f.metric} · ` : ""}${f.responsible_segment.dimension}=${f.responsible_segment.value} (${f.responsible_segment.pct_deviation >= 0 ? "+" : ""}${(f.responsible_segment.pct_deviation * 100).toFixed(1)}%)`
                    )
                    .join("; ")}`
                  : `${formatHour(h.hod)}: nothing stood out`
                return (
                  <button
                    key={h.hour}
                    type="button"
                    className="group relative flex-1 rounded-sm transition-opacity hover:opacity-100"
                    style={{
                      height: "2.25rem",
                      background,
                      opacity: isSelected ? 1 : flagged ? 0.85 : 0.5,
                      outline: isSelected ? "2px solid hsl(var(--foreground))" : "none",
                    }}
                    disabled={!flagged}
                    onClick={() => setSelected(isSelected ? null : h)}
                    title={title}
                  />
                )
              })}
            </div>
            <div className="mt-1 flex text-[9px] leading-none text-muted-foreground">
              {hours.map((h, i) => (
                <span key={h.hour} className="flex-1 text-center">
                  {i % 3 === 0 ? formatHour(h.hod) : ""}
                </span>
              ))}
            </div>

            {metric === "all" && (
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {METRICS.slice(1).map((m) => (
                  <span key={m.value} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                    <span className="inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: METRIC_COLOR[m.value] }} />
                    {m.label}
                  </span>
                ))}
              </div>
            )}

            {selected && flagsFor(selected, metric).length > 0 && (
              <div className="mt-3 space-y-1.5 rounded-md border bg-muted/30 px-3 py-2 text-xs">
                <span className="font-semibold">{formatHour(selected.hod)}</span>
                {flagsFor(selected, metric).map((f) => (
                  <div key={f.metric} className="flex items-center justify-between gap-2">
                    <span>
                      {metric === "all" && (
                        <span className="mr-1.5 inline-flex items-center gap-1 font-medium">
                          <span
                            className="inline-block h-2 w-2 rounded-sm"
                            style={{ backgroundColor: METRIC_COLOR[f.metric] }}
                          />
                          {f.metric} ·
                        </span>
                      )}
                      <span className="font-medium">
                        {f.responsible_segment.dimension} = {String(f.responsible_segment.value)}
                      </span>{" "}
                      <span className={f.responsible_segment.pct_deviation >= 0 ? "text-emerald-600" : "text-red-600"}>
                        ({f.responsible_segment.pct_deviation >= 0 ? "+" : ""}
                        {(f.responsible_segment.pct_deviation * 100).toFixed(1)}%)
                      </span>
                    </span>
                    <button
                      type="button"
                      className="shrink-0 rounded-md border px-2 py-1 text-[11px] hover:bg-muted"
                      onClick={() => onInvestigate?.({ metric: f.metric, day })}
                    >
                      Investigate
                    </button>
                  </div>
                ))}
              </div>
            )}
            {!loading && flaggedCount === 0 && (
              <p className="mt-2 text-xs text-muted-foreground">No hour stood out past threshold on this day.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
