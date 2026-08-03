import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import MetricTree from "@/components/MetricTree"
import AnomalyList from "@/components/AnomalyList"
import InvestigationDetail from "@/components/InvestigationDetail"
import MetricHistoryTimeline from "@/components/MetricHistoryTimeline"
import RevenueSignals from "@/components/RevenueSignals"
import AnomalyCountChart from "@/components/AnomalyCountChart"
import LatencyStats from "@/components/LatencyStats"
import HourScanStrip from "@/components/HourScanStrip"
import { listAnomalyCandidates, triggerScan, investigate, getMetricTree } from "@/api/client"

const METRIC_FILTERS = [
  { value: "all", label: "All metrics" },
  { value: "revenue", label: "Revenue" },
  { value: "fill_rate", label: "Fill rate" },
  { value: "render_rate", label: "Render rate" },
  { value: "ecpm", label: "eCPM" },
  { value: "ctr", label: "CTR" },
]

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function App() {
  const [day, setDay] = useState(() => localStorage.getItem("wdim_day") || "2026-07-05")
  const [tree, setTree] = useState([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [anomalies, setAnomalies] = useState([])
  const [anomaliesLoading, setAnomaliesLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [investigating, setInvestigating] = useState(false)
  const [investigatingId, setInvestigatingId] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [searchText, setSearchText] = useState("")
  const [metricFilter, setMetricFilter] = useState("all")
  const [scanCoverage, setScanCoverage] = useState(null)
  const [latencyRefreshKey, setLatencyRefreshKey] = useState(0)

  // Shared date range for Anomaly history + Anomaly counts, reported up by
  // MetricHistoryTimeline once it fetches.
  const [timelineDays, setTimelineDays] = useState([])
  const [timelineFrom, setTimelineFrom] = useState("")
  const [timelineTo, setTimelineTo] = useState("")

  const handleTimelineDaysLoaded = useCallback((days) => {
    const dayStrings = days.map((d) => d.day)
    setTimelineDays(dayStrings)
    setTimelineFrom((prev) => prev || dayStrings[0] || "")
    setTimelineTo((prev) => prev || dayStrings[dayStrings.length - 1] || "")
  }, [])

  const investigationRef = useRef(null)

  const timelineMin = timelineDays[0]
  const timelineMax = timelineDays[timelineDays.length - 1]

  function resetTimelineRange() {
    setTimelineFrom(timelineMin || "")
    setTimelineTo(timelineMax || "")
  }

  const filteredAnomalies = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    return anomalies.filter((a) => {
      if (metricFilter !== "all" && a.metric !== metricFilter) return false
      if (!q) return true
      const segmentText = Object.entries(a.segment_dims || {})
        .map(([k, v]) => `${k} ${v}`)
        .join(" ")
        .toLowerCase()
      return a.metric.toLowerCase().includes(q) || segmentText.includes(q)
    })
  }, [anomalies, searchText, metricFilter])

  const loadTree = useCallback(async (d) => {
    setTreeLoading(true)
    try {
      setTree(await getMetricTree({ day: d }))
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setTreeLoading(false)
    }
  }, [])

  const loadAnomalies = useCallback(async (d) => {
    setAnomaliesLoading(true)
    try {
      setAnomalies(await listAnomalyCandidates({ day: d }))
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setAnomaliesLoading(false)
    }
  }, [])

  useEffect(() => {
    localStorage.setItem("wdim_day", day)
      ; (async () => {
        await loadTree(day)
        await loadAnomalies(day)
      })()
  }, [day, loadTree, loadAnomalies])

  async function handleScan() {
    setScanning(true)
    setError(null)
    try {
      const res = await triggerScan({})
      setScanCoverage(res?.coverage || null)
      await loadAnomalies(day)
      await loadTree(day)
    } catch (e) {
      setError(e.message)
    } finally {
      setScanning(false)
    }
  }

  function scrollToInvestigation() {
    investigationRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  async function runInvestigate({ metric, day: investigateDay, anomalyCandidateId }) {
    setError(null)
    setResult(null)
    if (anomalyCandidateId) setInvestigatingId(anomalyCandidateId)
    else setInvestigating(true);

    try {
      setTimeout(scrollToInvestigation, 150)
      const res = await investigate({ metric, day: investigateDay, anomalyCandidateId })
      setResult(res)
      setLatencyRefreshKey((k) => k + 1)
      setTimeout(scrollToInvestigation, 150)
      setTimeout(scrollToInvestigation, 600)
    } catch (e) {
      setError(e.message)
    } finally {
      setInvestigatingId(null)
      setInvestigating(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-lg" />
          <div>
            <h1 className="text-xl font-semibold">Why Did It Move</h1>
            <p className="text-sm text-muted-foreground">Automated root-cause analysis on ClickHouse - InMobi ad-metrics</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={day}
            onChange={(e) => setDay(e.target.value)}
            className="h-8 w-32 text-xs"
          />
          <Button variant="outline" size="sm" onClick={() => setDay(todayIso())}>
            Today
          </Button>
          <Button size="sm" onClick={handleScan} disabled={scanning}>
            {scanning ? "Scanning…" : "Re-scan"}
          </Button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <LatencyStats refreshKey={latencyRefreshKey} />

      {scanCoverage && (scanCoverage.partial_days?.length > 0 || scanCoverage.skipped_insufficient_history > 0) && (
        <div className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
          <div className="font-semibold">Detection coverage</div>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {scanCoverage.partial_days?.map((p) => (
              <li key={p.day}>{p.note || `${p.day} is only partially loaded.`}</li>
            ))}
            {scanCoverage.skipped_insufficient_history > 0 && (
              <li>
                {scanCoverage.skipped_insufficient_history.toLocaleString()} segment-days skipped: fewer than{" "}
                {scanCoverage.min_baseline_samples} prior same-weekday observations to compare against. Not evaluated,
                not cleared.
              </li>
            )}
          </ul>
        </div>
      )}

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold uppercase text-muted-foreground">Metric tree - {day}</h2>
        <MetricTree tree={tree} loading={treeLoading} />
      </section>

      <section className="mb-6">
        <HourScanStrip day={day} onInvestigate={({ metric, day: d }) => runInvestigate({ metric, day: d })} />
      </section>

      <section className="mb-6">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Anomaly timelines</h2>
          <div className="flex items-center gap-1">
            <Input
              type="date"
              value={timelineFrom}
              min={timelineMin}
              max={timelineTo || timelineMax}
              onChange={(e) => setTimelineFrom(e.target.value)}
              className="h-8 w-32 text-xs"
            />
            <span className="text-xs text-muted-foreground">to</span>
            <Input
              type="date"
              value={timelineTo}
              min={timelineFrom || timelineMin}
              max={timelineMax}
              onChange={(e) => setTimelineTo(e.target.value)}
              className="h-8 w-32 text-xs"
            />
            {(timelineFrom !== timelineMin || timelineTo !== timelineMax) && (
              <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={resetTimelineRange}>
                Reset range
              </Button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <MetricHistoryTimeline
            onInvestigate={({ metric, day: d }) => runInvestigate({ metric, day: d })}
            investigating={investigating}
            fromDay={timelineFrom}
            toDay={timelineTo}
            onDaysLoaded={handleTimelineDaysLoaded}
          />
          <AnomalyCountChart
            onInvestigate={runInvestigate}
            allDays={timelineDays}
            fromDay={timelineFrom}
            toDay={timelineTo}
          />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>
              Flagged anomalies {anomalies.length > 0 && `(${filteredAnomalies.length}/${anomalies.length})`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-2 flex gap-2">
              <Input
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search segment, e.g. gaming or country…"
                className="h-8 flex-1 text-xs"
              />
              <Select value={metricFilter} onValueChange={setMetricFilter}>
                <SelectTrigger className="h-8 w-32 shrink-0 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {METRIC_FILTERS.map((m) => (
                    <SelectItem key={m.value} value={m.value}>
                      {m.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="scroll-thin max-h-[28rem] overflow-y-auto pr-1">
              <AnomalyList
                anomalies={filteredAnomalies}
                loading={anomaliesLoading}
                investigatingId={investigatingId}
                onInvestigate={(a) => runInvestigate({ metric: a.metric, day: a.day, anomalyCandidateId: a.id })}
                emptyMessage={
                  anomalies.length > 0
                    ? "No anomalies match this search/filter."
                    : "No flagged anomalies for this day. Try Re-scan, or click a day on the right to investigate it manually."
                }
              />
            </div>
          </CardContent>
        </Card>

        <RevenueSignals day={day} onInvestigate={runInvestigate} />
      </div>

      <section ref={investigationRef} className="mt-6 scroll-mt-4">
        <h2 className="mb-2 text-sm font-semibold uppercase text-muted-foreground">Investigation</h2>
        <InvestigationDetail result={result} loading={investigating || investigatingId != null} />
      </section>
    </div>
  )
}
