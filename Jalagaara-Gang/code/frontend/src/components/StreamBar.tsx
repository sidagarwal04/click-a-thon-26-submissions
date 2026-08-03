import type { SegmentFinding, StreamDetection, StreamStatus } from "../api";

function pct(value: number): string {
  return `${value < 0 ? "−" : "+"}${Math.abs(value * 100).toFixed(1)}%`;
}

function hourLabel(iso: string): string {
  return iso.replace("T", " ").slice(5, 16); // "07-09 02:00"
}

interface FoldedHit {
  metric: string;
  hours: number;
  from: string;
  to: string;
  avgPct: number;
}

// One sustained move is ONE finding, not one per hour. Detection runs hourly, so a drop lasting
// half a day reported 14 separate "anomalies" for a single incident — and rpr/ecpm, both
// revenue-denominated, doubled that again. The full-dataset sweep merges contiguous windows and
// folds echoes; this is the streaming equivalent, done per metric.
function foldByMetric(detections: StreamDetection[]): FoldedHit[] {
  const byMetric = new Map<string, StreamDetection[]>();
  for (const d of detections) {
    const list = byMetric.get(d.metric) ?? [];
    list.push(d);
    byMetric.set(d.metric, list);
  }
  return [...byMetric.entries()]
    .map(([metric, list]) => {
      const sorted = [...list].sort((a, b) => a.hour.localeCompare(b.hour));
      return {
        metric,
        hours: sorted.length,
        from: sorted[0].hour,
        to: sorted[sorted.length - 1].hour,
        avgPct: sorted.reduce((sum, d) => sum + d.pct_delta, 0) / sorted.length,
      };
    })
    .sort((a, b) => Math.abs(b.avgPct) - Math.abs(a.avgPct));
}

// Real-time mode. Shown only while a replay is live (or just finished), so the dashboard looks
// exactly as before when nothing is streaming. Detections appear newest-first as they are found
// — the point of the mode is watching them arrive, not reading a report afterwards.
export function StreamBar({ stream, onStop }: { stream: StreamStatus; onStop: () => void }) {
  const done = stream.batches_done ?? 0;
  const total = stream.batches_total ?? 0;
  const progress = total ? Math.round((done / total) * 100) : 0;
  const live = stream.status === "running";
  const hits = foldByMetric(stream.detections ?? []);

  return (
    <div className={`stream-bar ${live ? "is-live" : ""}`} role="status">
      <div className="sb-head">
        <span className="sb-title">
          {live && <span className="sb-pulse" />}
          {live ? "Real-time mode" : `Replay ${stream.status}`}
        </span>
        <span className="sb-meta mono">
          {done}/{total} batches · {(stream.rows_ingested ?? 0).toLocaleString()} events ·{" "}
          {stream.checks ?? 0} checks
          {stream.current_window && ` · ${hourLabel(stream.current_window[0])}`}
          {stream.last_tick_ms != null && ` · ${stream.last_tick_ms}ms/tick`}
        </span>
        {live && (
          <button className="ghost-btn sb-stop" onClick={onStop}>Stop</button>
        )}
      </div>

      <div className="sb-track" aria-label={`${progress}% replayed`}>
        <div className="sb-fill" style={{ width: `${progress}%` }} />
      </div>

      {stream.error && <div className="sb-error">Stream error: {stream.error}</div>}

      {(stream.segment_findings?.length ?? 0) > 0 && (
        <div className="sb-hits">
          <span className="eyebrow">
            Deep scan · {stream.segment_findings!.length} findings
            {stream.deep_scans ? ` · pass ${stream.deep_scans}` : ""}
          </span>
          <div className="sb-hit-list">
            {stream.segment_findings!.map((f: SegmentFinding, i: number) => (
              <span key={`${f.metric}-${i}`} className={`sb-hit ${f.scope === "segment" ? "is-segment" : ""}`}>
                <span className="mono">{f.metric}</span>
                <span className={f.peak_pct_delta < 0 ? "is-drop" : "is-spike"}>{pct(f.peak_pct_delta)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {hits.length > 0 ? (
        <div className="sb-hits">
          <span className="eyebrow">
            {hits.length} anomal{hits.length === 1 ? "y" : "ies"} detected live
            {" · "}
            {(stream.detections?.length ?? 0)} firing hours
          </span>
          <div className="sb-hit-list">
            {hits.map((h) => (
              <span key={h.metric} className="sb-hit">
                <span className="mono">{h.metric}</span>
                <span className={h.avgPct < 0 ? "is-drop" : "is-spike"}>{pct(h.avgPct)}</span>
                <span className="sb-hit-hour mono">
                  {hourLabel(h.from)}
                  {h.hours > 1 && ` → ${hourLabel(h.to)} · ${h.hours}h`}
                </span>
              </span>
            ))}
          </div>
        </div>
      ) : (
        live && <div className="sb-waiting">Scoring each hour as it lands — nothing anomalous yet.</div>
      )}
    </div>
  );
}
