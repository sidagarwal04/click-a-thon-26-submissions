import { useState } from "react"
import { MessageCircle, Download, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import PlaybackTimeline from "@/components/PlaybackTimeline"
import ChatBox from "@/components/ChatBox"
import LatencyBar from "@/components/LatencyBar"
import { buildInvestigationPdf, downloadPdf } from "@/lib/report"

const KIND_COLOR = {
  overall: "hsl(var(--primary))",
  factor: "#f59e0b",
  segment: "#ef4444",
  combo: "#f43f5e",
}

function buildComparisonRows(result) {
  const rows = []
  if (result.overall) {
    rows.push({ label: `${result.overall.metric} (overall)`, kind: "overall", ...result.overall })
  }
  for (const f of result.driving_factors || []) {
    if (result.overall && f.metric === result.overall.metric && f.pct_deviation === result.overall.pct_deviation) continue
    rows.push({ label: f.metric, kind: "factor", ...f })
  }
  if (result.responsible_segment) {
    const s = result.responsible_segment
    rows.push({ label: `${s.dimension} = ${s.value}`, kind: "segment", actual: s.actual, baseline: s.baseline, pct_deviation: s.pct_deviation })
    if (s.refined_by) {
      const r = s.refined_by
      rows.push({ label: `↳ ${r.dimension} = ${r.value}`, kind: "combo", actual: r.actual, baseline: r.baseline, pct_deviation: r.pct_deviation })
    }
  }
  return rows.filter((r) => r.pct_deviation != null)
}

export default function InvestigationDetail({ result, loading }) {
  const [showPlayback, setShowPlayback] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [showEvidence, setShowEvidence] = useState(false)

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-4 text-sm text-muted-foreground">
          Running detect → drill-down → narrate pipeline…
        </CardContent>
      </Card>
    )
  }

  if (!result) {
    return (
      <Card>
        <CardContent className="pt-4 text-sm text-muted-foreground">
          Select an anomaly to investigate, or run one manually.
        </CardContent>
      </Card>
    )
  }

  const { diagnosis_text, responsible_segment, driving_factors, checked_and_ruled_out, langfuse_trace_id } = result
  const langfuseBase = import.meta.env.VITE_LANGFUSE_URL || "http://localhost:3000"
  const langfuse_trace_url = result.langfuse_trace_url || (langfuse_trace_id ? `${langfuseBase}/trace/${langfuse_trace_id}` : null)

  function handleDownload() {
    const doc = buildInvestigationPdf(result, langfuse_trace_url)
    downloadPdf(doc, `investigation-${result.metric}-${result.day}.pdf`)
  }

  const evidence = { overall: result.overall, driving_factors, responsible_segment, checked_and_ruled_out }
  const comparisonRows = buildComparisonRows(result)
  const maxAbsRowDeviation = Math.max(0.01, ...comparisonRows.map((r) => Math.abs(r.pct_deviation)))

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>Diagnosis</CardTitle>
          <CardDescription>{result.metric} · {result.day}</CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={handleDownload}
          title="Download report (PDF)"
        >
          <Download className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {result.data_coverage_note && (
          <div className="flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
            <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0 text-amber-600" />
            <span>{result.data_coverage_note}</span>
          </div>
        )}

        <p className="text-sm leading-relaxed">{diagnosis_text}</p>

        <LatencyBar timings={result.timings} />

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {result.confidence != null && (
            <span>
              Confidence <span className="font-medium text-foreground tabular-nums">{result.confidence.toFixed(2)}</span>
            </span>
          )}
          {result.overall?.baseline_n != null && (
            <span>
              Baseline from{" "}
              <span className="font-medium text-foreground tabular-nums">{result.overall.baseline_n}</span>{" "}
              prior same-weekday{result.overall.baseline_n === 1 ? "" : "s"}
            </span>
          )}
          {result.overall?.evaluated_hours && (
            <span>
              Hours compared <span className="font-medium text-foreground">{result.overall.evaluated_hours}</span>
            </span>
          )}
        </div>

        {responsible_segment && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Responsible segment</h4>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="destructive">
                {responsible_segment.dimension} = {String(responsible_segment.value)} (
                {responsible_segment.pct_deviation >= 0 ? "+" : ""}
                {(responsible_segment.pct_deviation * 100).toFixed(1)}%)
              </Badge>
              {responsible_segment.refined_by && (
                <>
                  <span className="text-xs text-muted-foreground">further localized to</span>
                  <Badge variant="destructive">
                    {responsible_segment.refined_by.dimension} = {String(responsible_segment.refined_by.value)} (
                    {responsible_segment.refined_by.pct_deviation >= 0 ? "+" : ""}
                    {(responsible_segment.refined_by.pct_deviation * 100).toFixed(1)}%)
                  </Badge>
                </>
              )}
            </div>
          </div>
        )}

        {comparisonRows.length > 0 && (
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Overall vs. factors vs. segment - actual vs. baseline
            </h4>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2 py-1">
                {comparisonRows.map((r) => {
                  const widthPct = Math.min(50, (Math.abs(r.pct_deviation) / maxAbsRowDeviation) * 50)
                  const isPositive = r.pct_deviation >= 0
                  return (
                    <div key={r.label} className="flex items-center gap-2">
                      <span className="w-28 shrink-0 truncate text-right text-[10px] text-muted-foreground" title={r.label}>
                        {r.label}
                      </span>
                      <div className="relative h-4 flex-1">
                        <div className="absolute inset-y-0 left-1/2 w-px bg-muted-foreground/30" />
                        <div
                          className="absolute inset-y-0 rounded-sm"
                          style={{
                            [isPositive ? "left" : "right"]: "50%",
                            width: `${widthPct}%`,
                            backgroundColor: KIND_COLOR[r.kind],
                          }}
                        />
                      </div>
                      <span
                        className={`w-14 shrink-0 text-right text-[10px] font-medium tabular-nums ${
                          isPositive ? "text-emerald-600" : "text-red-600"
                        }`}
                      >
                        {isPositive ? "+" : ""}
                        {(r.pct_deviation * 100).toFixed(1)}%
                      </span>
                    </div>
                  )
                })}
              </div>
              <div className="scroll-thin overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-1 pr-2 font-medium">Segment / factor</th>
                      <th className="py-1 pr-2 font-medium">Actual</th>
                      <th className="py-1 pr-2 font-medium">Baseline</th>
                      <th className="py-1 font-medium">Deviation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map((r) => (
                      <tr key={r.label} className="border-b last:border-0">
                        <td className="py-1.5 pr-2">{r.label}</td>
                        <td className="py-1.5 pr-2 tabular-nums">{r.actual != null ? r.actual.toFixed(4) : "-"}</td>
                        <td className="py-1.5 pr-2 tabular-nums">{r.baseline != null ? r.baseline.toFixed(4) : "-"}</td>
                        <td className={`py-1.5 tabular-nums font-medium ${r.pct_deviation >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                          {r.pct_deviation >= 0 ? "+" : ""}
                          {(r.pct_deviation * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {checked_and_ruled_out?.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Checked and ruled out</h4>
            <ul className="list-inside list-disc space-y-0.5 text-xs text-muted-foreground">
              {checked_and_ruled_out.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowPlayback(true)}>
            ▶ Replay this incident
          </Button>
          {langfuse_trace_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={langfuse_trace_url} target="_blank" rel="noreferrer">
                Open full trace in Langfuse
              </a>
            </Button>
          )}
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setChatOpen(true)}>
            <MessageCircle className="h-3.5 w-3.5" />
            Ask a follow-up
          </Button>
        </div>

        <div className="border-t pt-3">
          <button
            type="button"
            onClick={() => setShowEvidence((v) => !v)}
            className="flex items-center gap-1 text-xs font-semibold uppercase text-muted-foreground hover:text-foreground"
          >
            {showEvidence ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            Raw evidence (JSON fed to the LLM)
          </button>
          {showEvidence && (
            <pre className="scroll-thin mt-2 max-h-64 overflow-auto rounded-md bg-muted p-3 text-[11px] leading-relaxed">
              {JSON.stringify(evidence, null, 2)}
            </pre>
          )}
        </div>
      </CardContent>

      <Dialog open={showPlayback} onOpenChange={setShowPlayback}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Replay: {result.metric} · {result.day}</DialogTitle>
            <DialogDescription>
              {responsible_segment
                ? `Overall vs ${responsible_segment.dimension} = ${responsible_segment.value}`
                : "Overall metric, hour by hour"}
            </DialogDescription>
          </DialogHeader>
          {showPlayback && (
            <PlaybackTimeline metric={result.metric} day={result.day} segment={responsible_segment} />
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={chatOpen} onOpenChange={setChatOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ask a follow-up</DialogTitle>
            <DialogDescription>Parsed by the LLM, answered from ClickHouse.</DialogDescription>
          </DialogHeader>
          {chatOpen && (
            <ChatBox
              key={result.langfuse_trace_id || `${result.metric}-${result.day}`}
              context={{
                metric: result.metric,
                day: result.day,
                dimension: responsible_segment?.dimension || null,
                value: responsible_segment?.value != null ? String(responsible_segment.value) : null,
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  )
}
