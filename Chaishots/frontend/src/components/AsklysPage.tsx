import {
  ArrowRight,
  ArrowUpRight,
  AtSign,
  BarChart3,
  BrainCircuit,
  Check,
  ChevronDown,
  Database,
  GitBranch,
  LineChart,
  LoaderCircle,
  MessageSquareText,
  Paperclip,
  PlaneTakeoff,
  Plus,
  Send,
  Sparkles,
  Table2,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import "../asklys.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { askAsklys, fetchAsklysContext } from "../api";
import type {
  AsklysContextItem,
  AsklysContextRef,
  AsklysActivityEvent,
  AsklysFunnelStep,
  AsklysPathLink,
  AsklysResponse,
  AsklysTrendSeries,
} from "../types";

type ChatMessage =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; response: AsklysResponse };

const suggestions = [
  { icon: BarChart3, label: "Build a conversion funnel", prompt: "Show me the main user conversion funnel" },
  { icon: LineChart, label: "Find a trend", prompt: "Trend daily active users over time" },
  { icon: GitBranch, label: "Explore user paths", prompt: "Show the most common user paths after application_started" },
  { icon: MessageSquareText, label: "Ask about the data", prompt: "What data is available in this ClickHouse database?" },
];

export function AsklysPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [contextItems, setContextItems] = useState<AsklysContextItem[]>([]);
  const [selectedContext, setSelectedContext] = useState<AsklysContextItem[]>([]);
  const [database, setDatabase] = useState("ClickHouse");
  const [contextOpen, setContextOpen] = useState(false);
  const [contextQuery, setContextQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [liveActivity, setLiveActivity] = useState<AsklysActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const threadEnd = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchAsklysContext("", controller.signal)
      .then((result) => { setContextItems(result.items); setDatabase(result.database); })
      .catch((reason) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load ClickHouse context"); });
    return () => controller.abort();
  }, []);

  useEffect(() => { threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, loading, liveActivity]);

  const filteredContext = useMemo(() => {
    const needle = contextQuery.toLowerCase().replace(/^@/, "");
    return contextItems.filter((item) => !selectedContext.some((selected) => selected.label === item.label) && (!needle || item.label.toLowerCase().includes(needle))).slice(0, 12);
  }, [contextItems, contextQuery, selectedContext]);

  function updateQuestion(value: string) {
    setQuestion(value);
    const mention = value.match(/@([\w.]*)$/);
    if (mention) { setContextQuery(mention[1]); setContextOpen(true); }
  }

  function attach(item: AsklysContextItem) {
    setSelectedContext((current) => [...current, item]);
    setQuestion((current) => current.replace(/@[\w.]*$/, `${item.label} `));
    setContextOpen(false);
    setContextQuery("");
    textarea.current?.focus();
  }

  async function submit(nextQuestion = question) {
    const prompt = nextQuestion.trim();
    if (!prompt || loading) return;
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: prompt };
    const history = messages.slice(-10).map((message) => ({ role: message.role, content: message.content }));
    setMessages((current) => [...current, userMessage]);
    setQuestion(""); setContextOpen(false); setError(null); setLiveActivity([]); setLoading(true);
    try {
      const response = await askAsklys({
        question: prompt,
        context: selectedContext.map<AsklysContextRef>((item) => ({ kind: item.kind, table: item.table, column: item.column })),
        conversation: history,
      }, (event) => {
        if (event.type === "status") setLiveActivity((current) => [...current, event]);
      });
      setLiveActivity([]);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: response.answer, response }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Asklys could not answer that question");
    } finally { setLoading(false); }
  }

  function resetChat() {
    setMessages([]); setQuestion(""); setSelectedContext([]); setError(null); setLiveActivity([]);
  }

  return (
    <main className="asklys-page">
      <aside className="asklys-sidebar">
        <button className="asklys-new-chat" onClick={resetChat}><Plus size={15} /> New chat</button>
        <div className="asklys-sidebar-label">Today</div>
        <button className="asklys-thread-row asklys-thread-row--active"><MessageSquareText size={14} /><span>{messages.find((item) => item.role === "user")?.content ?? "New conversation"}</span></button>
        <div className="asklys-source-card"><Database size={15} /><div><span>Connected source</span><strong>{database}</strong></div><i /></div>
      </aside>

      <section className={`asklys-main ${messages.length ? "asklys-main--thread" : ""}`}>
        <div className="asklys-mobile-head"><button onClick={resetChat}><Plus size={14} /> New chat</button><span><i /> {database}</span></div>
        {messages.length === 0 ? (
          <div className="asklys-intro">
            <div className="asklys-orb"><PlaneTakeoff size={25} /></div>
            <p className="eyebrow">Asklys · AI product analyst</p>
            <h1>What do you want to know?</h1>
            <p className="asklys-subtitle">Ask a question in plain English. Asklys understands the tables in <strong>{database}</strong> and turns the answer into the right view.</p>
            <div className="asklys-suggestions">{suggestions.map(({ icon: Icon, label, prompt }) => <button key={label} onClick={() => void submit(prompt)}><Icon size={15} /><span>{label}</span><ArrowRight size={13} /></button>)}</div>
          </div>
        ) : (
          <div className="asklys-thread">
            {messages.map((message) => message.role === "user" ? <div className="asklys-user-message" key={message.id}>{message.content}</div> : <AssistantMessage key={message.id} response={message.response} />)}
            {(loading || (error && liveActivity.length > 0)) && <LiveActivity events={liveActivity} failed={!loading && Boolean(error)} />}
            <div ref={threadEnd} />
          </div>
        )}

        <div className={`asklys-composer-wrap ${messages.length ? "asklys-composer-wrap--sticky" : ""}`}>
          {error && <div className="asklys-error"><span>{error}</span><button onClick={() => setError(null)}><X size={13} /></button></div>}
          <div className="asklys-composer">
            {selectedContext.length > 0 && <div className="asklys-context-chips">{selectedContext.map((item) => <span key={item.label}>{item.kind === "table" ? <Table2 size={11} /> : <AtSign size={11} />}{item.label.slice(1)}<button onClick={() => setSelectedContext((current) => current.filter((entry) => entry.label !== item.label))}><X size={10} /></button></span>)}</div>}
            <textarea ref={textarea} value={question} onChange={(event) => updateQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder="Ask anything about your product data…" rows={2} />
            <div className="asklys-composer-actions">
              <div>
                <button className={contextOpen ? "active" : ""} onClick={() => { setContextOpen(!contextOpen); setContextQuery(""); }} title="Attach ClickHouse context"><Paperclip size={15} /> Attach</button>
                <span>Type <kbd>@</kbd> to add context</span>
                <span className="asklys-model-badge"><BrainCircuit size={12} /> DeepSeek V4 Pro</span>
              </div>
              <button className="asklys-send" onClick={() => void submit()} disabled={!question.trim() || loading}>{loading ? <LoaderCircle className="spin" size={16} /> : <Send size={15} />}</button>
            </div>
            {contextOpen && <ContextMenu items={filteredContext} query={contextQuery} onQuery={setContextQuery} onSelect={attach} onClose={() => setContextOpen(false)} />}
          </div>
          <p className="asklys-notice">Asklys can make mistakes. Verify important decisions and generated SQL.</p>
        </div>
      </section>
    </main>
  );
}

function LiveActivity({ events, failed }: { events: AsklysActivityEvent[]; failed: boolean }) {
  const latest = events.at(-1);
  return <div className="asklys-thinking asklys-live-activity">
    <span className={`asklys-avatar ${failed ? "asklys-avatar--failed" : ""}`}>{failed ? <X size={15} /> : <Sparkles size={15} />}</span>
    <div className="asklys-activity-body">
      <div className="asklys-activity-head">
        <div><strong>{failed ? "Asklys stopped" : latest?.message ?? "Starting Asklys"}</strong><small>{events.length ? `${events.length} live ${events.length === 1 ? "step" : "steps"}` : "Connecting to the analyst"}</small></div>
        {!failed && <LoaderCircle className="spin" size={14} />}
      </div>
      <ol className="asklys-activity-list">
        {events.map((event, index) => {
          const current = index === events.length - 1 && !failed;
          return <li key={`${event.stage}-${index}`} className={current ? "active" : ""}>
            <span>{current ? <LoaderCircle className="spin" size={11} /> : <Check size={10} />}</span>
            <div><b>{activityLabel(event.stage)}</b><p>{event.message}</p>
              {event.detail && <small>{event.detail}</small>}
              {event.sql && <details><summary>Generated SQL <ChevronDown size={11} /></summary><pre>{event.sql}</pre></details>}
            </div>
          </li>;
        })}
      </ol>
    </div>
  </div>;
}

function ContextMenu({ items, query, onQuery, onSelect, onClose }: { items: AsklysContextItem[]; query: string; onQuery: (value: string) => void; onSelect: (item: AsklysContextItem) => void; onClose: () => void }) {
  return <div className="asklys-context-menu">
    <div className="asklys-context-search"><AtSign size={14} /><input autoFocus value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Find a table or column" /><button onClick={onClose}><X size={13} /></button></div>
    <div className="asklys-context-title"><span>ClickHouse context</span><small>{items.length} matches</small></div>
    <div className="asklys-context-results">{items.length ? items.map((item) => <button key={item.label} onClick={() => onSelect(item)}><span>{item.kind === "table" ? <Table2 size={14} /> : <AtSign size={14} />}</span><div><strong>{item.label}</strong><small>{item.description}</small></div><Plus size={13} /></button>) : <p>No matching context</p>}</div>
  </div>;
}

function AssistantMessage({ response }: { response: AsklysResponse }) {
  return <article className="asklys-assistant-message">
    <span className="asklys-avatar"><Sparkles size={15} /></span>
    <div className="asklys-answer-body">
      <div className="asklys-answer-kicker">{intentLabel(response.intent)} <span>·</span> {response.database}</div>
      <h2>{response.title}</h2>
      <div className="asklys-reasoning">
        <div className="asklys-reasoning-head"><BrainCircuit size={14} /><strong>Analysis complete</strong><span>{response.query_attempts ? `${response.query_attempts} ${response.query_attempts === 1 ? "query" : "queries"}` : "Schema response"}</span></div>
        <ol>{response.analysis_steps.map((step, index) => <li key={`${step}-${index}`}><span><Check size={10} /></span><p>{step}</p></li>)}</ol>
      </div>
      <p>{response.answer}</p>
      {response.visualization?.kind === "funnel" && <FunnelChart steps={response.visualization.funnel} />}
      {response.visualization?.kind === "trend" && <TrendChart series={response.visualization.series} />}
      {response.visualization?.kind === "user_path" && <PathChart links={response.visualization.paths} />}
      {response.sql && <details className="asklys-sql"><summary><span>View query</span><ChevronDown size={13} /></summary><pre>{response.sql}</pre></details>}
      <div className="asklys-answer-meta">
        {response.context_used.length > 0 && <div className="asklys-used-context"><Paperclip size={11} /> Used {response.context_used.join(", ")}</div>}
        {response.langfuse_trace_id && <a className="asklys-trace-link" href={`/?run=${encodeURIComponent(response.langfuse_trace_id)}`}><Sparkles size={11} /> View Langfuse trace <ArrowUpRight size={11} /></a>}
      </div>
    </div>
  </article>;
}

function FunnelChart({ steps }: { steps: AsklysFunnelStep[] }) {
  const totalConversion = steps.at(-1)?.conversion_rate ?? 0;
  return <div className="asklys-viz asklys-funnel">
    <header><div><span>Ordered funnel</span><strong>Conversion by step</strong></div><div className="asklys-funnel-summary"><small>Overall conversion</small><strong>{formatPercent(totalConversion)}</strong></div></header>
    {steps.length ? <div className="asklys-funnel-scroll"><div className="asklys-funnel-grid" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(220px, 1fr))` }}>
      <div className="asklys-funnel-gridlines"><i /><i /><i /><i /><span>100%</span><span>75%</span><span>50%</span><span>25%</span></div>
      {steps.map((step, index) => <section className="asklys-funnel-stage" key={`${step.name}-${index}`}>
        <div className="asklys-funnel-bar-zone"><div className="asklys-funnel-column" title={`${step.name}: ${formatNumber(step.value)} users`}><i className="asklys-funnel-backdrop" /><i className="asklys-funnel-fill" style={{ height: `${Math.max(2, step.conversion_rate * 100)}%` }} /><b style={{ bottom: `calc(${Math.max(2, step.conversion_rate * 100)}% + 7px)` }}>{formatPercent(step.conversion_rate)}</b></div></div>
        <footer className="asklys-funnel-legend-v2">
          <div className="asklys-funnel-event"><span>{index + 1}</span><strong>{humanize(step.name)}</strong></div>
          <div className="asklys-funnel-converted"><TrendingUp size={13} /><span><strong>{formatNumber(step.value)}</strong> users {index > 0 && <em>({formatPercent(step.conversion_rate)})</em>}</span></div>
          {index > 0 && <div className="asklys-funnel-dropped"><TrendingDown size={13} /><span><strong>{formatNumber(step.dropoff)}</strong> dropped <em>({formatPercent(step.dropoff_rate)})</em></span></div>}
        </footer>
      </section>)}
    </div></div> : <EmptyViz />}
  </div>;
}

function TrendChart({ series }: { series: AsklysTrendSeries[] }) {
  const values = series.flatMap((item) => item.points.map((point) => point.y));
  const max = Math.max(...values, 1); const width = 680; const height = 230; const pad = 30;
  const colors = ["#6f4ed6", "#e97835", "#2f8a58", "#367bbd"];
  return <div className="asklys-viz asklys-trend">
    <header><div><span>Trend</span><strong>Change over time</strong></div><div className="asklys-legend">{series.map((item, index) => <small key={item.name}><i style={{ background: colors[index % colors.length] }} />{item.name}</small>)}</div></header>
    {values.length ? <div className="asklys-trend-canvas"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trend chart"><g className="asklys-grid">{[0, 1, 2, 3, 4].map((line) => <line key={line} x1={pad} x2={width - pad} y1={pad + line * 42} y2={pad + line * 42} />)}</g>{series.map((item, seriesIndex) => { const points = item.points.map((point, index) => `${pad + (index / Math.max(1, item.points.length - 1)) * (width - pad * 2)},${height - pad - (point.y / max) * (height - pad * 2)}`).join(" "); return <g key={item.name}><polyline points={points} fill="none" stroke={colors[seriesIndex % colors.length]} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />{item.points.map((point, index) => <circle key={`${point.x}-${index}`} cx={pad + (index / Math.max(1, item.points.length - 1)) * (width - pad * 2)} cy={height - pad - (point.y / max) * (height - pad * 2)} r="3.5" fill="#fff" stroke={colors[seriesIndex % colors.length]} strokeWidth="2"><title>{point.x}: {formatNumber(point.y)}</title></circle>)}</g>; })}</svg><div className="asklys-axis"><span>{series[0]?.points[0]?.x}</span><span>{series[0]?.points.at(-1)?.x}</span></div></div> : <EmptyViz />}
  </div>;
}

function PathChart({ links }: { links: AsklysPathLink[] }) {
  const max = Math.max(...links.map((link) => link.value), 1);
  return <div className="asklys-viz asklys-path"><header><div><span>User path</span><strong>Most common transitions</strong></div><small>{links.length} paths</small></header>
    {links.length ? <div className="asklys-path-list">{links.map((link, index) => <div className="asklys-path-row" key={`${link.source}-${link.target}-${index}`}><div className="asklys-path-node"><span>{index + 1}</span><strong>{link.source}</strong></div><div className="asklys-path-edge"><small>{formatNumber(link.value)} users</small><i><b style={{ width: `${Math.max(8, link.value / max * 100)}%` }} /></i><ArrowRight size={14} /></div><div className="asklys-path-node asklys-path-node--target"><strong>{link.target}</strong></div></div>)}</div> : <EmptyViz />}
  </div>;
}

function EmptyViz() { return <div className="asklys-empty-viz">No matching data for this view.</div>; }
function formatNumber(value: number) { return new Intl.NumberFormat("en", { notation: value >= 10000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value); }
function formatPercent(value: number) { return new Intl.NumberFormat("en", { style: "percent", maximumFractionDigits: 1 }).format(value); }
function humanize(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function activityLabel(stage: string) {
  const labels: Record<string, string> = { schema: "Schema", planning: "Plan", intent: "Intent", query: "ClickHouse", review: "Review", repair: "Repair", accepted: "Validated", summary: "Answer" };
  return labels[stage] ?? humanize(stage);
}
function intentLabel(intent: AsklysResponse["intent"]) { return intent === "user_path" ? "User path" : intent[0].toUpperCase() + intent.slice(1); }
