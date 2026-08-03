import { AlertTriangle, ArrowRight, BarChart3, Check, Code2, Database, GitBranch, Lightbulb, Link2, Rows3, Table2 } from "lucide-react";
import { useState } from "react";
import { titleCase } from "../format";
import type { JsonValue, RunReport } from "../types";

type JsonObject = Record<string, JsonValue>;
type ReportTab = "overview" | "profile" | "schema" | "context" | "analyses" | "insights";

export function RunReportView({ tab, report }: { tab: ReportTab; report: RunReport }) {
  if (tab === "overview") return <Overview report={report} />;
  if (tab === "profile") return <Profile artifact={object(report.artifacts.event_profile)} />;
  if (tab === "schema") return <Schema artifact={object(report.artifacts.schema)} plan={object(report.artifacts.instrumentation_plan)} />;
  if (tab === "context") return <Context artifact={object(report.artifacts.context_diff)} />;
  if (tab === "analyses") return <Analyses plans={object(report.artifacts.analysis_plan)} proposed={object(report.artifacts.proposed_analysis_plan)} results={array(report.artifacts.query_results)} />;
  return <Insights artifact={object(report.artifacts.insights)} />;
}

function Overview({ report }: { report: RunReport }) {
  const insights = array(object(report.artifacts.insights).insights).map(object);
  const artifacts = report.artifacts;
  const stages = [
    ["Profiled events", "event_profile", Rows3],
    ["Generated schema", "schema", Table2],
    ["Updated context", "context_diff", GitBranch],
    ["Executed analysis", "query_results", BarChart3],
    ["Produced insights", "insights", Lightbulb],
  ] as const;
  return <div className="report-stack">
    <section className="output-summary">
      <div className="output-summary__intro"><span className="report-eyebrow">Pipeline output</span><h3>What this run produced</h3><p>The final persisted result from ClickHouse, linked to this Langfuse trace.</p></div>
      <div className="output-stats"><OutputStat label="Status" value={report.summary.status} /><OutputStat label="Rows loaded" value={report.summary.rows_loaded.toLocaleString()} /><OutputStat label="Table" value={report.summary.table_created || "Not created"} mono /><OutputStat label="Context" value={report.summary.context_version ? `v${report.summary.context_version}` : "—"} /></div>
    </section>
    <section className="artifact-flow">
      {stages.map(([label, key, Icon], index) => <div className={`artifact-stage ${artifacts[key] ? "artifact-stage--done" : ""}`} key={key}><span><Icon size={15} /></span><div><small>0{index + 1}</small><strong>{label}</strong></div>{artifacts[key] && <Check size={14} />}{index < stages.length - 1 && <ArrowRight className="artifact-arrow" size={14} />}</div>)}
    </section>
    <section className="insight-preview"><div className="section-heading"><div><span className="report-eyebrow">Decision support</span><h3>Top insights</h3></div><span>{insights.length} generated</span></div>
      {insights.length ? <div className="insight-preview-grid">{insights.slice(0, 3).map((insight, index) => <article key={String(insight.title ?? index)}><div><Lightbulb size={15} /><Confidence value={String(insight.confidence ?? "unknown")} /></div><h4>{String(insight.title ?? "Untitled insight")}</h4><p>{String(insight.interpretation ?? insight.observation ?? "")}</p><strong>Recommendation</strong><span>{String(insight.recommendation ?? "No recommendation captured")}</span></article>)}</div> : <EmptyArtifact label="No detailed insights were stored for this run." />}
    </section>
  </div>;
}

function Profile({ artifact }: { artifact: JsonObject }) {
  const profile = object(artifact.profile);
  const eventCount = number(profile.event_count);
  const events = Object.entries(object(profile.event_names)).sort((a, b) => number(b[1]) - number(a[1]));
  const fields = Object.entries(object(profile.fields));
  if (!Object.keys(profile).length) return <EmptyArtifact label="The event profile is not available yet." />;
  return <div className="report-stack">
    <section className="report-section"><div className="section-heading"><div><span className="report-eyebrow">Ingestion input</span><h3>Event distribution</h3></div><span>{eventCount.toLocaleString()} total events</span></div><div className="event-bars">{events.map(([name, countValue]) => { const count = number(countValue); const pct = eventCount ? count / eventCount * 100 : 0; return <div className="event-bar" key={name}><div><strong>{titleCase(name)}</strong><span>{count.toLocaleString()} · {pct.toFixed(1)}%</span></div><i><b style={{ width: `${pct}%` }} /></i></div>; })}</div></section>
    <section className="report-section"><div className="section-heading"><div><span className="report-eyebrow">Field inspection</span><h3>Observed fields</h3></div><span>{fields.length} columns profiled</span></div><div className="artifact-table-wrap"><table className="artifact-table"><thead><tr><th>Field</th><th>Type</th><th>Presence</th><th>Cardinality</th><th>Examples</th></tr></thead><tbody>{fields.map(([name, raw]) => { const field = object(raw); return <tr key={name}><td className="mono">{name}</td><td><TypeBadge value={String(field.observed_type ?? "unknown")} /></td><td>{(number(field.presence) * 100).toFixed(1)}%</td><td>{number(field.approx_cardinality).toLocaleString()}{field.cardinality_is_estimate ? " ~" : ""}</td><td className="examples">{array(field.examples).slice(0, 3).map(String).join(", ") || "—"}</td></tr>; })}</tbody></table></div><div className="profile-provenance"><span>Spec SHA-256 <code>{String(artifact.spec_sha256 ?? "—")}</code></span><span>Baseline tables <strong>{array(artifact.available_tables).length}</strong></span></div></section>
  </div>;
}

function Schema({ artifact, plan }: { artifact: JsonObject; plan: JsonObject }) {
  const columns = Object.entries(object(artifact.schema));
  if (!columns.length) return <EmptyArtifact label="The generated schema is not available yet." />;
  return <div className="report-stack"><section className="report-section"><div className="schema-hero"><span><Database size={20} /></span><div><small>ClickHouse destination</small><h3>{String(artifact.table_name ?? "Generated table")}</h3><p>{columns.length} typed columns generated and validated before ingestion.</p></div></div><div className="contract-grid"><OutputStat label="Primary entity" value={String(plan.primary_entity ?? "—")} mono /><OutputStat label="Timestamp" value={String(plan.timestamp_field ?? "—")} mono /><OutputStat label="Order by" value={array(plan.order_by).map(String).join(", ") || "—"} mono /><OutputStat label="Funnel steps" value={String(array(plan.funnel_steps).length)} /></div><div className="funnel-contract">{array(plan.funnel_steps).map((step, index) => <span key={index}><small>{index + 1}</small>{String(step)}{index < array(plan.funnel_steps).length - 1 && <ArrowRight size={11} />}</span>)}</div><div className="artifact-table-wrap"><table className="artifact-table"><thead><tr><th>Column</th><th>ClickHouse type</th><th>Nullable</th></tr></thead><tbody>{columns.map(([name, rawType]) => { const type = String(rawType); return <tr key={name}><td className="mono">{name}</td><td className="mono type-code">{type}</td><td>{type.startsWith("Nullable(") ? "Yes" : "No"}</td></tr>; })}</tbody></table></div></section><CodeBlock title="Executed DDL" code={String(artifact.ddl ?? "")} /></div>;
}

function Context({ artifact }: { artifact: JsonObject }) {
  const relationships = array(artifact.relationships_added).map(object);
  const metrics = array(artifact.metrics_added).map(object);
  const conflicts = array(artifact.conflicts);
  if (!Object.keys(artifact).length) return <EmptyArtifact label="The context update is not available yet." />;
  return <div className="report-stack"><section className="report-section"><div className="section-heading"><div><span className="report-eyebrow">Semantic graph</span><h3>Relationships added</h3></div><span>{relationships.length} joins</span></div><div className="relationship-list">{relationships.map((item, index) => <article key={index}><span><Link2 size={15} /></span><div className="relationship-path"><code>{String(item.source_table)}.{String(item.source_column)}</code><ArrowRight size={13} /><code>{String(item.target_table)}.{String(item.target_column)}</code><p>{String(item.reason ?? "")}</p></div></article>)}</div></section><section className="report-section"><div className="section-heading"><div><span className="report-eyebrow">Reusable definitions</span><h3>Metrics added</h3></div><span>{metrics.length} metrics</span></div><div className="metrics-catalog">{metrics.map((metric, index) => <article key={index}><h4>{titleCase(String(metric.name ?? "Metric"))}</h4><p>{String(metric.description ?? "")}</p><div><span>Numerator<code>{String(metric.numerator ?? "—")}</code></span><span>Denominator<code>{String(metric.denominator ?? "—")}</code></span></div><small>Dimensions · {array(metric.dimensions).map(String).join(", ") || "none"}</small></article>)}</div></section>{conflicts.length > 0 && <section className="conflicts"><AlertTriangle size={16} /><div><strong>{conflicts.length} context conflicts</strong><p>{conflicts.map(String).join(" · ")}</p></div></section>}</div>;
}

function Analyses({ plans, proposed, results }: { plans: JsonObject; proposed: JsonObject; results: JsonValue[] }) {
  const analyses = array(plans.analyses).map(object);
  const proposals = array(proposed.analyses).map(object);
  const resultMap = new Map(results.map((raw) => { const item = object(raw); return [String(item.query_id), item]; }));
  if (!analyses.length) return <EmptyArtifact label="The validated analysis plan is not available yet." />;
  return <div className="analysis-list"><div className="section-heading analysis-heading"><div><span className="report-eyebrow">Validated execution</span><h3>Analyses and aggregate results</h3></div><span>{proposals.length} proposed → {analyses.length} validated</span></div><div className="proposal-strip"><span>Agent proposal</span>{proposals.map((proposal, index) => <code key={index}>{titleCase(String(proposal.query_id ?? `Query ${index + 1}`))}</code>)}</div>{analyses.map((analysis, index) => <AnalysisCard key={String(analysis.query_id ?? index)} analysis={analysis} result={resultMap.get(String(analysis.query_id))} index={index} />)}</div>;
}

function AnalysisCard({ analysis, result, index }: { analysis: JsonObject; result?: JsonObject; index: number }) {
  const [open, setOpen] = useState(index === 0);
  const rows = array(result?.rows);
  return <article className={`analysis-card ${open ? "analysis-card--open" : ""}`}><button onClick={() => setOpen(!open)}><span><Code2 size={15} /></span><div><small>{String(analysis.analysis_type ?? "analysis")}</small><strong>{titleCase(String(analysis.query_id ?? `Query ${index + 1}`))}</strong><p>{String(analysis.purpose ?? "")}</p></div><b>{rows.length.toLocaleString()} rows</b><i>{open ? "−" : "+"}</i></button>{open && <div className="analysis-detail"><CodeBlock title="Validated SQL" code={String(analysis.sql ?? "")} />{rows.length > 0 ? <ResultMatrix rows={rows} /> : <EmptyArtifact label="This query returned no rows." />}</div>}</article>;
}

function Insights({ artifact }: { artifact: JsonObject }) {
  const insights = array(artifact.insights).map(object);
  if (!insights.length) return <EmptyArtifact label="Detailed insights are not available yet." />;
  return <div className="full-insights"><div className="section-heading"><div><span className="report-eyebrow">Analytics agent output</span><h3>Evidence-backed insights</h3></div><span>{insights.length} insights</span></div>{insights.map((insight, index) => <article key={index}><header><span>0{index + 1}</span><div><h4>{String(insight.title ?? "Untitled insight")}</h4><Confidence value={String(insight.confidence ?? "unknown")} /></div></header><div className="insight-body"><InsightField label="Observation" value={String(insight.observation ?? "")} /><InsightField label="Interpretation" value={String(insight.interpretation ?? "")} /><InsightField label="Recommendation" value={String(insight.recommendation ?? "")} accent /><InsightList label="Evidence" values={array(insight.evidence)} /><InsightList label="Caveats" values={array(insight.caveats)} /></div></article>)}</div>;
}

function OutputStat({ label, value, mono }: { label: string; value: string; mono?: boolean }) { return <div><span>{label}</span><strong className={mono ? "mono" : ""}>{value}</strong></div>; }
function Confidence({ value }: { value: string }) { return <span className={`confidence confidence--${value.toLowerCase()}`}>{value} confidence</span>; }
function TypeBadge({ value }: { value: string }) { return <span className="type-badge">{value}</span>; }
function EmptyArtifact({ label }: { label: string }) { return <div className="report-empty"><Database size={18} /><span>{label}</span></div>; }
function CodeBlock({ title, code }: { title: string; code: string }) { return <section className="code-block"><div><Code2 size={13} /><span>{title}</span></div><pre>{code || "No code stored"}</pre></section>; }
function ResultMatrix({ rows }: { rows: JsonValue[] }) { const matrix = rows.map(array); const width = Math.max(...matrix.map((row) => row.length)); return <div className="result-matrix"><div className="result-matrix__title"><Table2 size={13} />Aggregate output</div><div className="artifact-table-wrap"><table className="artifact-table"><thead><tr>{Array.from({ length: width }, (_, index) => <th key={index}>Value {index + 1}</th>)}</tr></thead><tbody>{matrix.slice(0, 100).map((row, rowIndex) => <tr key={rowIndex}>{Array.from({ length: width }, (_, columnIndex) => <td key={columnIndex}>{display(row[columnIndex])}</td>)}</tr>)}</tbody></table></div>{matrix.length > 100 && <small>Showing the first 100 of {matrix.length} rows.</small>}</div>; }
function InsightField({ label, value, accent }: { label: string; value: string; accent?: boolean }) { return <section className={accent ? "insight-field--accent" : ""}><strong>{label}</strong><p>{value || "—"}</p></section>; }
function InsightList({ label, values }: { label: string; values: JsonValue[] }) { if (!values.length) return null; return <section><strong>{label}</strong><ul>{values.map((value, index) => <li key={index}>{display(value)}</li>)}</ul></section>; }
function object(value: JsonValue | undefined): JsonObject { return value !== null && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {}; }
function array(value: JsonValue | undefined): JsonValue[] { return Array.isArray(value) ? value : []; }
function number(value: JsonValue | undefined): number { return typeof value === "number" ? value : Number(value ?? 0) || 0; }
function display(value: JsonValue | undefined): string { if (value == null) return "—"; return typeof value === "object" ? JSON.stringify(value) : String(value); }

export type { ReportTab };
