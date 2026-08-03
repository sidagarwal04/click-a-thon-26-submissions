import { useEffect, useRef, useState } from "react";
import { getBundle, getHealth, getSeries, getStreamStatus, getTrace, listBundles, listIncidents,
         setDataset, startRangeInvestigation, startStream, stopStream, waitForRangeInvestigation,
         type IncidentRow, type SeriesPoint, type StreamStatus } from "./api";
import { AnomalyCard } from "./components/AnomalyCard";
import { DiagnosisCard } from "./components/DiagnosisCard";
import { FactorSplit } from "./components/FactorSplit";
import { MetricTree } from "./components/MetricTree";
import { RuledOutPanel } from "./components/RuledOutPanel";
import { SidebarDock } from "./components/SidebarDock";
import { TraceDrawer } from "./components/TraceDrawer";
import { StreamBar } from "./components/StreamBar";
import { ClickathonMark } from "./components/ClickathonMark";
import { DateField } from "./components/DateField";
import type { EvidenceBundle, InvestigationRow } from "./types";

// Langfuse's worker ingests spans asynchronously; give it this long before snapshotting.
const TRACE_SNAPSHOT_DELAY_MS = 10000;
// Engine status is a live condition, so re-poll it rather than trusting page load.
const HEALTH_POLL_MS = 30000;
// Ticks are ~1-2.5s, so poll a touch faster than a batch to keep the bar honest.
const STREAM_POLL_MS = 1500;
// Survives the post-seed reload so the fresh finding is what gets showcased, not the biggest.
const SHOWCASE_KEY = "rca-showcase-id";

// Read and consume the handoff at MODULE load, not inside the mount effect. StrictMode
// double-invokes effects in dev, so consuming it there let the second pass see null, fall back
// to "biggest move", and overwrite the first pass's selection — the fresh finding never showed.
// Module scope evaluates exactly once per page load, so both passes read the same value.
const SEEDED_SHOWCASE_ID = (() => {
  const id = sessionStorage.getItem(SHOWCASE_KEY);
  sessionStorage.removeItem(SHOWCASE_KEY); // one-shot: a later manual reload shows the biggest
  return id;
})();


// Bounds of the loaded dataset. Picking outside this range can only ever sweep empty hours, so
// the calendar refuses it up front instead of returning a confusing "no anomalies found".
const DATA_MIN_DATE = "2026-06-01";
const DATA_MAX_DATE = "2026-07-10";

function incidentLabel(row: IncidentRow): string {
  const date = row.window_start?.slice(5, 10) ?? "";
  const pct = `${row.pct_delta < 0 ? "−" : "+"}${Math.abs(row.pct_delta * 100).toFixed(1)}%`;
  let seg = "";
  try {
    const parsed = JSON.parse(row.localized_segment || "{}");
    const vals = Object.values(parsed);
    // Cap the segment list: a 4-dimension localization made the option so wide the control
    // overlapped the brand mark. The full segment is still on the card and in the tree.
    if (vals.length) seg = ` · ${vals.slice(0, 2).join(", ")}${vals.length > 2 ? "…" : ""}`;
  } catch {
    /* not JSON — leave the label unsegmented */
  }
  return `${row.metric} ${row.direction} ${pct} · ${date}${seg}`;
}

export default function App() {
  // Null until a real stored bundle loads. The dashboard used to seed this with
  // fixtures/sample_bundle.json, which rendered invented numbers that looked exactly like a real
  // diagnosis — the one thing this tool must never do. Empty state instead; see the JSX below.
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [booting, setBooting] = useState(true); // distinguishes "still loading" from "nothing there"
  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [engine, setEngine] = useState<"live" | "fixture" | "offline" | null>(null); // from /health
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState<number>(99); // drill-down reveal cursor
  const [activePanel, setActivePanel] = useState<"both" | "diagnosis" | "factor">("both");
  const [theme, setTheme] = useState<"dark" | "light">(
    () => (localStorage.getItem("rca-theme") as "dark" | "light") || "dark"
  );
  const [winStart, setWinStart] = useState("");
  const [winEnd, setWinEnd] = useState("");
  const [history, setHistory] = useState<InvestigationRow[]>([]);
  const [traceOpen, setTraceOpen] = useState(false);
  const [stream, setStream] = useState<StreamStatus | null>(null);
  const [dataset, setDatasetState] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<string[]>([]);
  const streamPoll = useRef<number | undefined>(undefined);
  const [series, setSeries] = useState<SeriesPoint[] | undefined>(undefined);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  // Theme lives on <body> so page backgrounds (not just cards) follow variables-final.css.
  // color-scheme keeps native controls (select, scrollbars) in sync with light/dark.
  useEffect(() => {
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
    document.body.style.colorScheme = theme;
    localStorage.setItem("rca-theme", theme);
  }, [theme]);

  // Real 24h actual-vs-expected series for the anomaly card. Keyed on the shown bundle; when the
  // backend can't serve it (offline, or the investigation isn't in the store) series stays
  // undefined and the card renders its synthetic fallback. `seriesLoading` gates the synthetic
  // curve so a bundle switch shows a blank skeleton while the fetch is in flight, instead of
  // flashing the fake curve for a frame. Guarded against a stale response overwriting a newer
  // bundle's series.
  const bundleId = bundle?.investigation_id;
  useEffect(() => {
    if (!bundleId) { setSeries(undefined); setSeriesLoading(false); return; }
    let cancelled = false;
    setSeries(undefined);
    setSeriesLoading(true);
    getSeries(bundleId).then((s) => {
      if (!cancelled) { setSeries(s?.points); setSeriesLoading(false); }
    });
    return () => { cancelled = true; };
  }, [bundleId]);

  // Localization strength: how much of the GLOBAL delta the culprit segment explains, i.e. the
  // product of each drill-down step's share of its parent's delta. Replaces the old
  // min(0.99, |z|/5), which saturated at 0.99 for every real anomaly (z-scores run into the tens
  // and hundreds). Undefined when nothing localized (population-wide move, empty drill-down).
  const localizationConfidence = bundle?.drilldown.length
    ? Math.min(1, bundle.drilldown.reduce((acc, n) => acc * Math.abs(n.contribution_pct ?? 0), 1))
    : undefined;

  const fd = bundle?.factor_decomposition;
  const depth = (bundle?.drilldown.length ?? 0) + 1; // + root
  const pctLabel = bundle
    ? `${bundle.anomaly.pct_delta < 0 ? "−" : "+"}${Math.abs(bundle.anomaly.pct_delta * 100).toFixed(1)}%`
    : "";

  const refreshHistory = () => listBundles(15).then(setHistory);

  // On mount: report the real engine status, load past investigations, and load the stored
  // anomaly list — showcasing the biggest move first so the headline card is never a flat run.
  // Exception: right after a seed run the page reloads itself, and the id it left in
  // sessionStorage wins, so the reload lands on what was just found rather than the biggest.
  useEffect(() => {
    getHealth().then((h) => { if (h) { setEngine(h.engine); setDatasetState(h.dataset?.target ?? null); setDatasets(h.dataset?.available ?? []); } });
    refreshHistory();
    const justSeeded = SEEDED_SHOWCASE_ID;
    listIncidents().then((rows) => {
      rows.sort((a, b) => Math.abs(b.pct_delta) - Math.abs(a.pct_delta));
      setIncidents(rows);
      // Anomalies exist → show the first (biggest) one. None → leave `bundle` null and let the
      // empty state tell the user to run an investigation, rather than inventing a sample.
      const showId = (justSeeded && rows.some((r) => r.investigation_id === justSeeded))
        ? justSeeded
        : rows[0]?.investigation_id;
      if (!showId) {
        setBooting(false);
        return;
      }
      const isFresh = justSeeded === showId;
      selectIncident(showId, isFresh);
      // Warm the trace snapshot. Reading /trace is what persists it to ClickHouse, and
      // Langfuse ingests spans asynchronously — so wait for the worker, then read once.
      if (isFresh) {
        window.setTimeout(() => void getTrace(showId), TRACE_SNAPSHOT_DELAY_MS);
      }
    }).catch(() => setBooting(false));
    // Re-check health on a timer. Engine status is a live condition, not a page-load fact: a
    // single cold/slow probe used to latch the "offline" banner until the next investigation,
    // long after the database was healthy again.
    const health = window.setInterval(
      () => getHealth().then((h) => { if (h) { setEngine(h.engine); setDatasetState(h.dataset?.target ?? null); setDatasets(h.dataset?.available ?? []); } }),
      HEALTH_POLL_MS,
    );
    // Pick up a replay already in flight (e.g. after a page refresh mid-stream).
    getStreamStatus().then((s) => {
      if (s && s.status === "running") { setStream(s); beginPolling(); }
    });
    return () => {
      window.clearInterval(timer.current);
      window.clearInterval(health);
      window.clearInterval(streamPoll.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Real-time mode: poll status, and refresh the incident feed so detections found mid-replay
  // show up in the switcher without waiting for the run to finish.
  const beginPolling = () => {
    window.clearInterval(streamPoll.current);
    let lastHits = -1;
    streamPoll.current = window.setInterval(async () => {
      const s = await getStreamStatus();
      if (!s) return;
      setStream(s);
      const hits = s.detections?.length ?? 0;
      if (hits !== lastHits) { lastHits = hits; listIncidents().then(setIncidents); refreshHistory(); }
      if (s.status !== "running") {
        window.clearInterval(streamPoll.current);
        listIncidents().then(setIncidents);
      }
    }, STREAM_POLL_MS);
  };

  const onStartStream = async () => {
    const s = await startStream();          // reset:true — truncates, then refills from scratch
    if (!s) return;
    setStream(s);
    setIncidents([]);                       // the old feed describes data that was just truncated
    beginPolling();
  };

  // The dataset is what everything queries, so it must be visible and switchable. A silent
  // revert to dev after a stream made "Find anomalies" return 0 over the streamed range.
  const onSwitchDataset = async (target: string) => {
    const d = await setDataset(target);
    if (d) {
      setDatasetState(d.target);
      listIncidents().then(setIncidents);
      refreshHistory();
    }
  };

  const onStopStream = async () => {
    const s = await stopStream();
    if (s) setStream(s);
  };

  // `reveal` animates the drill-down instead of showing it already solved — used only for a
  // bundle that was just seeded, so the post-reload landing still reads as a search.
  const selectIncident = (id: string, reveal = false) => {
    setSelectedId(id);
    getBundle(id)
      .then((b) => {
        if (b) {
          setBundle(b);
          if (reveal) {
            setRunning(true); // revealSteps clears this when the walk finishes
            revealSteps(b);
          } else {
            setStep(99);
          }
        }
      })
      .finally(() => setBooting(false));
  };

  // Reveal the drill-down one node at a time so the localization reads as a search, not a jump.
  const revealSteps = (b: EvidenceBundle) => {
    window.clearInterval(timer.current);
    setStep(0);
    const d = b.drilldown.length + 1;
    timer.current = window.setInterval(() => {
      setStep((s) => {
        const next = s + 1;
        if (next >= d) {
          window.clearInterval(timer.current);
          setRunning(false);
          return d;
        }
        return next;
      });
    }, 620);
  };

  // Run: exactly the dev tool's "Find anomalies" + "Seed bundles from these findings", called as
  // one job. Requires an explicit date range picked in the topbar first — no implicit fallback
  // range, so the button stays disabled until both dates are set (see the JSX below).
  const run = async (win?: { start: string; end: string }) => {
    const target = win ?? (winStart && winEnd
      ? { start: `${winStart}T00:00:00`, end: `${winEnd}T00:00:00` }
      : null);
    if (!target) return; // button is disabled for this case, but guard anyway
    setRunning(true);
    await runRange(target.start, target.end);
  };

  // The windowed flow: same server code path as dev's "Find anomalies" + "Seed bundles".
  // Idempotent server-side — anomalies already in `bundles` are skipped, only new ones seed.
  //
  // When the job finishes we reload the page once rather than patching state in place. The seed
  // writes a whole batch of new bundles server-side, and a full reload is the one refresh that
  // is guaranteed to pick up every one of them (switcher, history, engine status, trace links)
  // instead of whatever subset a hand-written re-fetch remembered to update. The bundle to
  // showcase is handed across the reload in sessionStorage, so we still land on the fresh
  // finding rather than defaulting to the biggest historical move.
  const runRange = async (start: string, end: string) => {
    try {
      const jobId = await startRangeInvestigation(start, end);
      if (!jobId) return; // backend unreachable — leave the current view alone
      const result = await waitForRangeInvestigation(jobId);
      const fresh = result?.bundles.find((x) => x.investigation_id && !x.skipped && !x.error);
      if (fresh?.investigation_id) {
        sessionStorage.setItem(SHOWCASE_KEY, fresh.investigation_id);
      }
      window.location.reload(); // remount re-reads /health, so engine + dataset refresh there
    } finally {
      setRunning(false);
    }
  };

  // Re-open a stored investigation from the history list (already narrated, fully revealed).
  const openRun = async (id: string) => {
    const b = await getBundle(id);
    if (b) {
      window.clearInterval(timer.current);
      setBundle(b);
      setSelectedId(id);
      setRunning(false);
      setStep(99);
    }
  };

  const stepLabel = running ? `drilling ${Math.min(step + 1, depth)}/${depth}` : `depth ${depth} · localized`;
  const engineLabel = engine ? `engine · ${engine}` : "clickhouse · —";
  const segOf = (row: InvestigationRow) => {
    try {
      const s = JSON.parse(row.localized_segment || "{}");
      const keys = Object.keys(s);
      return keys.length ? keys.map((k) => `${k}=${s[k]}`).join(" ∧ ") : "—";
    } catch {
      return "—";
    }
  };
  const shortId = bundle?.investigation_id ? bundle.investigation_id.slice(0, 8) : null;

  return (
    <div className="app spacing-default effect-smooth">
      <header className="topbar">
        <div className="brand">
          <span className="brand-logo"><ClickathonMark /></span>
          <div className="brand-titles">
            <span className="brand-name">RCA analyst</span>
            <span className="brand-sub">
              {shortId ? `live · clickhouse bundles · ${shortId}` : "no investigation loaded"}
            </span>
          </div>
        </div>
        <div className="topbar-actions">
          {incidents.length > 0 && (
            <select
              className="ghost-btn incident-select"
              value={selectedId ?? ""}
              onChange={(e) => selectIncident(e.target.value)}
              aria-label="Switch anomaly"
            >
              {incidents.map((row) => (
                <option key={row.investigation_id} value={row.investigation_id}>
                  {incidentLabel(row)}
                </option>
              ))}
            </select>
          )}
          <button
            className="ghost-btn icon-btn"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
          <span className="status-pill"><span className="live-dot" /> {engineLabel}</span>
          {dataset && (
            <select
              className={`ghost-btn dataset-pill ${dataset === "unseen" ? "is-unseen" : ""}`}
              value={dataset}
              onChange={(e) => onSwitchDataset(e.target.value)}
              disabled={stream?.status === "running"}
              aria-label="Dataset"
              title={
                stream?.status === "running"
                  ? "A replay is streaming into the unseen tables — stop it to switch"
                  : "Which table set investigations query. Baselines always read dev history."
              }
            >
              {(datasets.length ? datasets : [dataset]).map((d) => (
                <option key={d} value={d}>data · {d}</option>
              ))}
            </select>
          )}
          <div className="controls">
            <DateField
              value={winStart}
              onChange={setWinStart}
              aria-label="Window start"
              min={DATA_MIN_DATE}
              max={DATA_MAX_DATE}
            />
            <DateField
              value={winEnd}
              onChange={setWinEnd}
              aria-label="Window end"
              min={winStart || DATA_MIN_DATE}
              max={DATA_MAX_DATE}
            />
          </div>
          <button
            className="ghost-btn"
            onClick={() => setTraceOpen(true)}
            disabled={!selectedId}
            title={selectedId ? "How this was investigated" : "Select or run an investigation first"}
          >
            Open trace
          </button>
          <button className="ghost-btn" onClick={onStartStream} disabled={stream?.status === "running"}>
            {stream?.status === "running" ? "Streaming…" : "Start stream"}
          </button>
          <button
            className="primary-btn"
            onClick={() => run()}
            disabled={running || !winStart || !winEnd}
            title={!winStart || !winEnd ? "Pick a start and end date first" : undefined}
          >
            {running ? "Finding anomalies…" : "Find Anomalies"}
          </button>
        </div>
      </header>

      {engine === "offline" && (
        <div className="offline-banner" role="status">
          <span className="offline-dot" /> Data store offline — no investigations can be loaded or
          run. Check
          <code> CLICKHOUSE_* </code> in <code>.env</code>, then recreate the backend
          (<code>docker compose up -d backend</code>).
        </div>
      )}

      {stream && stream.status !== "idle" && (
        <StreamBar stream={stream} onStop={onStopStream} />
      )}

      {!booting && !bundle ? (
        <main className="main-grid main-grid--empty">
          <section className="card empty-state" role="status">
            <span className="eyebrow">No anomalies stored yet</span>
            <h2 className="empty-title">Nothing has been investigated yet</h2>
            <p className="empty-body">
              Pick a <strong>start</strong> and <strong>end</strong> date in the toolbar above, then
              hit <strong>Investigate</strong>. Every metric is swept globally and per segment; each
              real anomaly found is saved here with its evidence, drill-down and SQL.
            </p>
            <p className="empty-hint">
              Data covers {DATA_MIN_DATE} → {DATA_MAX_DATE}. Already-investigated windows are
              skipped, so re-running is safe.
            </p>
            {/* Named here too: which tables get investigated is decided BEFORE the first run,
                and the toolbar pill is easy to miss on an empty dashboard. */}
            <p className="empty-hint">
              Investigating <strong>{dataset ?? "…"}</strong>
              {dataset === "unseen"
                ? " (the streamed Jul 6–10 slice; baselines still read dev history)"
                : " (Jun 1 – Jul 5)"}
              . Change it with the <strong>data ·</strong> selector in the toolbar before you start.
            </p>
          </section>
        </main>
      ) : !bundle ? (
        <main className="main-grid main-grid--empty">
          <section className="card empty-state" role="status">
            <span className="eyebrow">Loading</span>
            <p className="empty-body">Fetching stored investigations…</p>
          </section>
        </main>
      ) : (
      <main className="main-grid">
        <section className="col-left">
          <AnomalyCard
            metric={bundle.metric}
            anomaly={bundle.anomaly}
            confidence={localizationConfidence}
            running={running}
            window={bundle.target_window}
            series={series}
            seriesLoading={seriesLoading}
          />
          <div
            className={`split-row active-${activePanel}`}
            onClick={(e) => {
              const card = (e.target as HTMLElement).closest(".card");
              if (!card || !card.parentElement) return;
              const cards = [...card.parentElement.querySelectorAll(".card")];
              const which = cards[0] === card ? "diagnosis" : "factor";
              setActivePanel((prev) => (prev === which ? "both" : which));
            }}
          >
            <DiagnosisCard narrative={bundle.narrative} />
            <FactorSplit factors={fd?.factors ?? []} primary={fd?.primary_factor ?? ""} totalPct={pctLabel} />
            <div className="split-nav" onClick={(e) => e.stopPropagation()}>
              <button
                className={`split-arrow ${activePanel === "factor" ? "is-active" : ""}`}
                aria-label="Expand factor split"
                onClick={() => setActivePanel("factor")}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
              <button
                className={`split-mid ${activePanel === "both" ? "is-active" : ""}`}
                aria-label="Reset to equal"
                onClick={() => setActivePanel("both")}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="6" width="6" height="12" rx="1.5" />
                  <rect x="14" y="6" width="6" height="12" rx="1.5" />
                </svg>
              </button>
              <button
                className={`split-arrow ${activePanel === "diagnosis" ? "is-active" : ""}`}
                aria-label="Expand diagnosis"
                onClick={() => setActivePanel("diagnosis")}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            </div>
          </div>
          <RuledOutPanel items={bundle.ruled_out} />
        </section>

        <aside className="col-right">
          <section className="card card--feature">
            <div className="eyebrow-row">
              <span className="eyebrow">Metric tree</span>
              <span className="hint">{stepLabel}</span>
            </div>
            <MetricTree metric={bundle.metric} anomaly={bundle.anomaly} nodes={bundle.drilldown} step={running ? step : undefined} />

            {bundle.localized_segment && Object.keys(bundle.localized_segment).length > 0 && (
              <div className="localized">
                <span className="eyebrow">Localized to</span>
                <div className="chips">
                  {Object.entries(bundle.localized_segment).map(([k, v]) => (
                    <span key={k} className="chip">{k} = {v}</span>
                  ))}
                </div>
              </div>
            )}
          </section>

          <SidebarDock history={history} onOpenRun={openRun} onRefresh={refreshHistory} segOf={segOf} bundleId={selectedId} />
        </aside>
      </main>
      )}

      <TraceDrawer
        investigationId={selectedId}
        traceUrl={bundle?.trace_url}
        open={traceOpen}
        onClose={() => setTraceOpen(false)}
      />
    </div>
  );
}
