import { useEffect, useRef, useState } from "react";
import { scanStatus, startScan, type ScanIncident, type ScanJob } from "../api";

const CloseIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const POLL_MS = 1500;

function pct(value: number): string {
  return `${value < 0 ? "−" : "+"}${Math.abs(value * 100).toFixed(1)}%`;
}

// "fill_rate[os_version=iOS 18.1]" -> the segment part, for a readable chip.
function segmentOf(row: ScanIncident): string {
  const inSeg = row.metric.match(/\[(.+)\]/);
  if (inSeg) return inSeg[1];
  const loc = row.localized;
  if (loc && !("error" in loc)) {
    const entries = Object.entries(loc);
    if (entries.length) return entries.map(([k, v]) => `${k}=${v}`).join(" ∧ ");
  }
  return "population-wide";
}

function baseMetric(metric: string): string {
  return metric.split("[")[0];
}

// Sweep a date range for anomalies the system finds itself — no ground-truth case list. This is
// the unseen-incident path, so it lives on the main dashboard, not only the dev console.
// Echoes (the same event seen through other dimensions) are folded away by the backend and shown
// separately, so the list reads as distinct findings rather than 120 views of one collapse.
export function SweepDrawer({
  open,
  onClose,
  start,
  end,
  onInvestigate,
}: {
  open: boolean;
  onClose: () => void;
  start: string;
  end: string;
  onInvestigate: (metric: string, windowStart: string, windowEnd: string) => void;
}) {
  const [job, setJob] = useState<ScanJob | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEchoes, setShowEchoes] = useState(false);
  const poll = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearInterval(poll.current), []);

  const run = async () => {
    if (!start || !end) {
      setError("Pick a start and end date first.");
      return;
    }
    setError(null);
    setJob(null);
    setRunning(true);
    const jobId = await startScan(start, end);
    if (!jobId) {
      setRunning(false);
      setError("Could not start the sweep — is the backend running?");
      return;
    }
    window.clearInterval(poll.current);
    poll.current = window.setInterval(async () => {
      const status = await scanStatus(jobId);
      if (!status) return;
      setJob(status);
      if (status.finished) {
        window.clearInterval(poll.current);
        setRunning(false);
      }
    }, POLL_MS);
  };

  const incidents = job?.result?.incidents ?? [];
  // Worst first: `score` is the backend's own severity ranking (|pct move| x volume), so the
  // biggest real incident leads the list rather than whatever the sweep happened to hit first.
  const bySeverity = (a: ScanIncident, b: ScanIncident) =>
    (b.score ?? 0) - (a.score ?? 0) || Math.abs(b.peak_pct_delta) - Math.abs(a.peak_pct_delta);
  const primaries = incidents.filter((i) => i.role === "primary").sort(bySeverity);
  const echoes = incidents.filter((i) => i.role !== "primary").sort(bySeverity);

  const row = (inc: ScanIncident, isAnomaly = false) => (
    <li key={inc.incident_id} className={`sweep-row ${isAnomaly ? "is-anomaly" : ""}`}>
      <div className="sw-head">
        <span className="sw-metric mono">{baseMetric(inc.metric)}</span>
        {isAnomaly && <span className="sw-badge">anomaly</span>}
        <span className={`sw-delta mono ${inc.peak_pct_delta < 0 ? "is-drop" : "is-spike"}`}>
          {pct(inc.peak_pct_delta)}
        </span>
      </div>
      <div className="sw-meta">
        <span>{inc.window_start.slice(0, 10)}</span>
        <span className="sw-seg">{segmentOf(inc)}</span>
      </div>
      <button
        className="sw-action"
        onClick={() => onInvestigate(baseMetric(inc.metric), inc.window_start, inc.window_end)}
      >
        Investigate →
      </button>
    </li>
  );

  return (
    <>
      <div className={`trace-scrim ${open ? "open" : ""}`} onClick={onClose} aria-hidden={!open} />
      <aside className={`trace-drawer ${open ? "open" : ""}`} role="dialog" aria-label="Find anomalies">
        <header className="trace-head">
          <div>
            <span className="eyebrow">Find anomalies</span>
            <div className="trace-sub">
              {start && end ? `${start} → ${end}` : "set a date range in the topbar"}
              {job?.result && (
                <span className="trace-score mono">
                  {job.result.primary_count} findings · {job.result.count} raw
                </span>
              )}
            </div>
          </div>
          <button className="dock-icon" onClick={onClose} aria-label="Close">{CloseIcon}</button>
        </header>

        <div className="trace-body">
          <button className="primary-btn sweep-run" onClick={run} disabled={running}>
            {running ? "Sweeping…" : "Sweep this window"}
          </button>
          {error && <div className="trace-empty">{error}</div>}
          {running && (
            <div className="trace-empty">
              Scanning every metric globally and per dimension — this takes a moment.
            </div>
          )}
          {!running && job?.status === "error" && <div className="trace-empty">Sweep failed: {job.log}</div>}
          {!running && job?.finished && primaries.length === 0 && (
            <div className="trace-empty">No anomalies found in this window.</div>
          )}

          {primaries.length > 0 && (
            <>
              <div className="sw-section">
                {primaries.length} anomal{primaries.length === 1 ? "y" : "ies"} · worst first
              </div>
              <ul className="sweep-list">{primaries.map((inc) => row(inc, true))}</ul>
            </>
          )}

          {echoes.length > 0 && (
            <>
              <button className="ts-toggle" onClick={() => setShowEchoes((v) => !v)}>
                {showEchoes ? "Hide" : "Show"} {echoes.length} echo{echoes.length === 1 ? "" : "es"} of these findings
              </button>
              {showEchoes && (
                <ul className="sweep-list is-echo">{echoes.map((inc) => row(inc, false))}</ul>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
