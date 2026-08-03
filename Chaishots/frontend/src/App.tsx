import { Activity, AlertTriangle, ListTree, MessageSquareText, PanelLeftClose, Plus, RotateCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchRun, fetchRuns } from "./api";
import { RunDetail } from "./components/RunDetail";
import { RunList } from "./components/RunList";
import { NewRunPage } from "./components/NewRunPage";
import { AsklysPage } from "./components/AsklysPage";
import type { RunDetail as RunDetailType, RunSummary } from "./types";

export function App() {
  const [page, setPage] = useState<"runs" | "new" | "asklys">(() => location.pathname === "/new-run" ? "new" : location.pathname === "/asklys" ? "asklys" : "runs");
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => new URLSearchParams(location.search).get("run"));
  const [detail, setDetail] = useState<RunDetailType | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 720);

  const loadRuns = useCallback(async (signal?: AbortSignal) => {
    setLoadingRuns(true); setError(null);
    try {
      const response = await fetchRuns(signal);
      setRuns(response.data);
      setSelectedId((current) => current && response.data.some((run) => run.id === current) ? current : response.data[0]?.id ?? null);
    } catch (reason) { if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Could not load runs"); }
    finally { if (!signal?.aborted) setLoadingRuns(false); }
  }, []);

  const loadDetail = useCallback(async (id: string, signal?: AbortSignal) => {
    setLoadingDetail(true); setError(null);
    try { setDetail(await fetchRun(id, signal)); }
    catch (reason) { if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Could not load run"); }
    finally { if (!signal?.aborted) setLoadingDetail(false); }
  }, []);

  useEffect(() => { const controller = new AbortController(); void loadRuns(controller.signal); return () => controller.abort(); }, [loadRuns]);
  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    const url = new URL(location.href); url.searchParams.set("run", selectedId); history.replaceState(null, "", url);
    void loadDetail(selectedId, controller.signal);
    return () => controller.abort();
  }, [selectedId, loadDetail]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? runs.filter((run) => [run.name, run.feature, run.id, run.pipeline_run_id, run.status].some((value) => value?.toLowerCase().includes(needle))) : runs;
  }, [query, runs]);

  const navigate = useCallback((nextPage: "runs" | "new" | "asklys", traceId?: string) => {
    const path = nextPage === "new" ? "/new-run" : nextPage === "asklys" ? "/asklys" : traceId ? `/?run=${encodeURIComponent(traceId)}` : "/";
    history.pushState(null, "", path);
    setPage(nextPage);
    if (traceId) setSelectedId(traceId);
    if (nextPage === "runs" && window.innerWidth <= 720) setSidebarOpen(false);
  }, []);

  useEffect(() => {
    const onPopState = () => setPage(location.pathname === "/new-run" ? "new" : location.pathname === "/asklys" ? "asklys" : "runs");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => { document.title = page === "asklys" ? "Asklys · Product analyst" : "Clickathon · Run Explorer"; }, [page]);

  return (
    <div className={`app ${sidebarOpen && page === "runs" ? "" : "app--collapsed"}`}>
      <header className="topbar">
        <button className="brand" onClick={() => navigate("runs")}><span className="brand-mark"><Activity size={18} /></span><span><strong>Clickathon</strong><small>Run explorer</small></span></button>
        <nav className="topnav"><button className={page === "runs" ? "active" : ""} onClick={() => navigate("runs")}><ListTree size={14} />Runs</button><button className={page === "new" ? "active" : ""} onClick={() => navigate("new")}><Plus size={14} />New run</button><button className={page === "asklys" ? "active" : ""} onClick={() => navigate("asklys")}><MessageSquareText size={14} />Asklys</button></nav>
        <div className="connection"><i /><span>{page === "asklys" ? "ClickHouse connected" : "Langfuse connected"}</span><span className="connection__divider" /><span>{page === "asklys" ? "Asklys ready" : `${runs.length} runs`}</span></div>
        {page === "runs" && <button className="icon-button" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle run sidebar"><PanelLeftClose size={17} /></button>}
      </header>
      {page === "asklys" ? <AsklysPage /> : page === "new" ? <NewRunPage onRunReady={(traceId) => { navigate("runs", traceId); void loadRuns(); }} /> : <div className="workspace">
        {sidebarOpen && (loadingRuns ? <aside className="run-panel skeleton-panel"><div /><div /><div /><div /></aside> : <RunList runs={filtered} selectedId={selectedId} query={query} onQueryChange={setQuery} onSelect={setSelectedId} />)}
        {error ? <State title="Run data unavailable" message={error} action={() => void loadRuns()} /> : loadingDetail && !detail ? <DetailSkeleton /> : detail ? <RunDetail run={detail} refreshing={loadingDetail} onRefresh={() => void loadDetail(detail.id)} /> : !loadingRuns ? <State title="No runs yet" message="New Clickathon traces will appear here as soon as the pipeline runs." /> : null}
      </div>}
    </div>
  );
}

function State({ title, message, action }: { title: string; message: string; action?: () => void }) { return <main className="state"><span>{title.includes("unavailable") ? <AlertTriangle size={24} /> : <Sparkles size={24} />}</span><h2>{title}</h2><p>{message}</p>{action && <button onClick={action}><RotateCw size={15} />Try again</button>}</main>; }
function DetailSkeleton() { return <main className="detail-page detail-skeleton"><div className="wide"/><div className="medium"/><section><div/><div/><div/><div/></section><div className="wide"/><div className="rows"/></main>; }
