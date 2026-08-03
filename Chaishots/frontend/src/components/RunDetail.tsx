import { Activity, ArrowUpRight, Box, CalendarClock, CircleDollarSign, Clock3, Hash, Layers3, RotateCw } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchRunReport } from "../api";
import { dateTime, duration, money, titleCase } from "../format";
import type { RunDetail as RunDetailType } from "../types";
import type { RunReport } from "../types";
import { ContextTransition } from "./ContextTransition";
import { JsonView } from "./JsonView";
import { RunReportView, type ReportTab } from "./RunReportViews";
import { Timeline } from "./Timeline";

type Tab = ReportTab | "timeline" | "raw";

export function RunDetail({ run, refreshing, onRefresh }: { run: RunDetailType; refreshing: boolean; onRefresh: () => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [report, setReport] = useState<RunReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const statusClass = run.status.toLowerCase().includes("error") ? "error" : "success";

  useEffect(() => {
    setTab("overview"); setReport(null); setReportError(null);
    if (!run.pipeline_run_id) return;
    const controller = new AbortController();
    setReportLoading(true);
    fetchRunReport(run.pipeline_run_id, controller.signal)
      .then(setReport)
      .catch((reason) => { if (!controller.signal.aborted) setReportError(reason instanceof Error ? reason.message : "Could not load ClickHouse output"); })
      .finally(() => { if (!controller.signal.aborted) setReportLoading(false); });
    return () => controller.abort();
  }, [run.id, run.pipeline_run_id]);

  const tabs: Array<{ id: Tab; label: string; count?: number }> = [
    { id: "overview", label: "Overview" },
    { id: "timeline", label: "Timeline", count: Math.max(0, run.observation_count - 1) },
    { id: "profile", label: "Data profile" },
    { id: "schema", label: "Schema" },
    { id: "context", label: "Context" },
    { id: "analyses", label: "Analyses" },
    { id: "insights", label: "Insights", count: report?.summary.insights.length },
    { id: "raw", label: "Raw trace" },
  ];
  return (
    <main className="detail-page">
      <header className="detail-header">
        <div className="breadcrumb"><span>Runs</span><span>/</span><span>{run.id.slice(0, 12)}</span></div>
        <div className="detail-title-row">
          <div><div className="title-line"><span className={`status-dot status-dot--${statusClass}`} /><h1>{run.feature || titleCase(run.name)}</h1><span className={`status-pill status-pill--${statusClass}`}>{run.status}</span></div><p>{titleCase(run.name)} · {run.environment || "default"} environment</p></div>
          <div className="header-actions"><button onClick={onRefresh} disabled={refreshing}><RotateCw className={refreshing ? "spin" : ""} size={15} />Refresh</button>{run.html_path && <a href={run.html_path} target="_blank" rel="noreferrer">Langfuse <ArrowUpRight size={14} /></a>}</div>
        </div>
      </header>

      <div className="metrics-grid">
        <Metric icon={<Clock3 size={16} />} label="Duration" value={duration(run.latency)} detail={`${run.observation_count} observations`} />
        <Metric icon={<Layers3 size={16} />} label="Steps" value={String(Math.max(0, run.observation_count - 1))} detail={`${run.observations.filter((o) => o.type === "AGENT").length} agent calls`} />
        <Metric icon={<CircleDollarSign size={16} />} label="Total cost" value={money(run.total_cost)} detail="reported by Langfuse" />
        <Metric icon={<CalendarClock size={16} />} label="Started" value={dateTime(run.timestamp)} detail={run.release || "No release tag"} />
      </div>

      <section className="run-facts">
        <Fact icon={<Hash size={13} />} label="Trace ID" value={run.id} mono />
        <Fact icon={<Box size={13} />} label="Pipeline run" value={run.pipeline_run_id || "Not captured"} mono />
        <Fact icon={<Activity size={13} />} label="Version" value={run.version || "Unversioned"} />
      </section>

      <ContextTransition
        artifact={report ? objectArtifact(report.artifacts.context_diff) : {}}
        unavailable={reportLoading ? "Loading the context update for this run…" : report ? null : run.pipeline_run_id ? "This run has no persisted report yet." : "This trace is not linked to a pipeline run, so its context update was not recorded."}
      />

      <nav className="tabs" aria-label="Run details">
        {tabs.map((item) => <button key={item.id} onClick={() => setTab(item.id)} className={tab === item.id ? "active" : ""}>{item.label}{item.count != null && <span>{item.count}</span>}</button>)}
      </nav>
      <section className="tab-content">
        {tab === "timeline" && <Timeline observations={run.observations} latency={run.latency} />}
        {tab === "raw" && <div className="raw-trace-grid"><DataPanel title="Run input" description="Payload captured on the root trace." value={run.input} /><DataPanel title="Run output" description="Final result returned by the pipeline." value={run.output} /><DataPanel title="Metadata" description="Environment, labels, and trace context." value={run.metadata} /></div>}
        {tab !== "timeline" && tab !== "raw" && (reportLoading ? <ReportSkeleton /> : report ? <RunReportView tab={tab} report={report} /> : <div className="report-unavailable"><Box size={20} /><h3>ClickHouse output unavailable</h3><p>{reportError || (run.pipeline_run_id ? "This run has no persisted report yet." : "This trace is not linked to a pipeline run ID.")}</p></div>)}
      </section>
    </main>
  );
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) { return <div className="metric"><span className="metric__icon">{icon}</span><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></div>; }
function Fact({ icon, label, value, mono }: { icon: React.ReactNode; label: string; value: string; mono?: boolean }) { return <div className="fact">{icon}<span>{label}</span><strong className={mono ? "mono" : ""}>{value}</strong></div>; }
function DataPanel({ title, description, value }: { title: string; description: string; value: RunDetailType["input"] }) { return <div className="data-panel"><div><h3>{title}</h3><p>{description}</p></div><JsonView value={value} /></div>; }
function ReportSkeleton() { return <div className="report-skeleton"><div/><div/><div/><div/></div>; }
function objectArtifact(value: RunReport["artifacts"][string] | undefined) { return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
