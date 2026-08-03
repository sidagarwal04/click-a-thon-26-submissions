import { useEffect, useState, useCallback } from "react"
import { Gauge, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { getLatencyStats } from "@/api/client"

function ms(v) {
  if (v == null) return "-"
  return v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`
}

export default function LatencyStats({ refreshKey }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    getLatencyStats({ endpoint: "investigate" })
      .then(setStats)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  if (error) return null
  if (!loading && (!stats || stats.n === 0)) {
    return (
      <div className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Gauge className="h-3.5 w-3.5" />
        No investigations logged yet - p95 latency appears after the first one runs.
      </div>
    )
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-1 rounded-md border bg-muted/30 px-3 py-2 text-xs">
      <span className="flex items-center gap-1.5 font-semibold uppercase text-muted-foreground">
        <Gauge className="h-3.5 w-3.5" />
        Investigate latency
      </span>
      {loading ? (
        <span className="text-muted-foreground">Loading…</span>
      ) : (
        <>
          <span>
            p50 <span className="font-medium tabular-nums">{ms(stats.p50_ms)}</span>
          </span>
          <span>
            p95 <span className="font-semibold tabular-nums text-foreground">{ms(stats.p95_ms)}</span>
          </span>
          <span>
            p99 <span className="font-medium tabular-nums">{ms(stats.p99_ms)}</span>
          </span>
          <span className="text-muted-foreground">
            (ClickHouse p95 <span className="tabular-nums">{ms(stats.p95_clickhouse_ms)}</span> · LLM p95{" "}
            <span className="tabular-nums">{ms(stats.p95_llm_ms)}</span>)
          </span>
          <span className="text-muted-foreground">
            across <span className="font-medium">{stats.n}</span> run{stats.n === 1 ? "" : "s"}
          </span>
        </>
      )}
      <Button variant="ghost" size="icon" className="ml-auto h-6 w-6" onClick={load} title="Refresh">
        <RefreshCw className="h-3 w-3" />
      </Button>
    </div>
  )
}
