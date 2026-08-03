import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const METRIC_LABELS = {
  revenue: "Revenue",
  fill_rate: "Fill rate",
  ecpm: "eCPM",
  ctr: "CTR",
}

function segmentLabel(segmentDims) {
  if (!segmentDims) return "-"
  const [dim, value] = Object.entries(segmentDims)[0] || []
  return dim ? `${dim} = ${value}` : "-"
}

export default function AnomalyList({
  anomalies,
  loading,
  onInvestigate,
  investigatingId,
  emptyMessage = "No flagged anomalies for this day. Try Re-scan, or investigate a metric manually.",
}) {
  if (loading) {
    return <p className="text-sm text-muted-foreground">Scanning for anomalies…</p>
  }
  if (!anomalies?.length) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <div className="space-y-2">
      {anomalies.map((a) => (
        <div key={a.id} className="w-[98%]">
          <Card  >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle>
                  {METRIC_LABELS[a.metric] || a.metric} · {segmentLabel(a.segment_dims)}
                </CardTitle>
                <Badge variant={a.pct_deviation < 0 ? "destructive" : "warning"}>
                  {a.pct_deviation >= 0 ? "+" : ""}
                  {(a.pct_deviation * 100).toFixed(1)}%
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                actual {a.actual_value.toFixed(4)} vs baseline {a.baseline_value.toFixed(4)} · z={a.z_score.toFixed(2)}
              </span>
              <Button
                size="sm"
                disabled={investigatingId === a.id}
                onClick={() => onInvestigate(a)}
              >
                {investigatingId === a.id ? "Investigating…" : "Investigate"}
              </Button>
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  )
}
