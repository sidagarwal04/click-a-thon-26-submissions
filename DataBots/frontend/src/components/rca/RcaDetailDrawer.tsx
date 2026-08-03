import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { AnomalyIncident, ChatMessage } from '../../types';
import { HumanLoopControls } from './HumanLoopControls';
import { MetricTreeVisualizer } from './MetricTreeVisualizer';
import { CH_SPANS } from './LangfuseTracePanel';
import { sendChatMessage, triggerRcaAnalysis } from '../../services/api';
import {
  BrainCircuit,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Terminal,
  Activity,
  ShieldCheck,
  FileText,
  MessageSquare,
  Send,
  Bot,
  User,
  Sparkles,
  Play,
  Code2,
  ChevronDown,
  ChevronUp,
  GitBranch,
  Layers,
  Zap,
} from 'lucide-react';

interface Props {
  anomaly: AnomalyIncident;
  onApprove: (id: string) => void;
  onFlagHallucination: (id: string, reason: string, feedback: string) => void;
  onOpenLangfuseTrace: () => void;
  onOpenChatAgent: () => void;
  onAnalysisComplete?: (updated: AnomalyIncident) => void;
  isTraceOpen?: boolean;
}

type Tab = 'overview' | 'segments' | 'chat' | 'trace';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'overview',  label: 'Overview',   icon: <Layers className="w-3.5 h-3.5" /> },
  { id: 'segments',  label: 'Segments',   icon: <Activity className="w-3.5 h-3.5" /> },
  { id: 'chat',      label: 'Chat Agent', icon: <MessageSquare className="w-3.5 h-3.5" /> },
  { id: 'trace',     label: 'Trace',      icon: <Terminal className="w-3.5 h-3.5" /> },
];

export const RcaDetailDrawer: React.FC<Props> = ({
  anomaly,
  onApprove,
  onFlagHallucination,
  onOpenLangfuseTrace,
  onAnalysisComplete,
  isTraceOpen,
}) => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [liveAnomaly, setLiveAnomaly] = useState<AnomalyIncident>(anomaly);

  const formatDateToLocalISO = (d: Date): string => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    const year = d.getFullYear();
    const month = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hours = pad(d.getHours());
    const minutes = pad(d.getMinutes());
    const seconds = pad(d.getSeconds());
    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
  };

  const getDefaultWindowTimes = () => {
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    return {
      start: formatDateToLocalISO(yesterday),
      end: formatDateToLocalISO(now),
    };
  };

  const toDatetimeLocal = (s?: string, fallbackDefault?: string): string => {
    if (!s) return fallbackDefault || formatDateToLocalISO(new Date());
    let str = s.replace(' ', 'T');
    if (str.length === 16) {
      str += ':00';
    }
    return str.substring(0, 19);
  };

  const defaults = getDefaultWindowTimes();
  const [windowStart, setWindowStart] = useState(defaults.start);
  const [windowEnd, setWindowEnd] = useState(defaults.end);
  const [isRunningAnalysis, setIsRunningAnalysis] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'c-1',
      sender: 'assistant',
      text: `I'm connected to ClickHouse via MCP. Ask me anything about the ${anomaly.metric} anomaly or any segment breakdown.`,
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLiveAnomaly(anomaly);
    const defs = getDefaultWindowTimes();
    setWindowStart(toDatetimeLocal(anomaly?.window_start, defs.start));
    setWindowEnd(toDatetimeLocal(anomaly?.window_end, defs.end));
  }, [anomaly]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleRunAnalysis = async () => {
    setIsRunningAnalysis(true);
    const toApiTs = (dt: string) => {
      let formatted = dt.replace('T', ' ');
      if (formatted.length === 16) formatted += ':00';
      return formatted.substring(0, 19);
    };
    const result = await triggerRcaAnalysis(liveAnomaly.metric || 'revenue', toApiTs(windowStart), toApiTs(windowEnd));
    const updated = { ...result, id: anomaly.id, humanReview: anomaly.humanReview };
    setLiveAnomaly(updated);
    // Notify parent so trace panel (and other consumers) get the fresh langfuse data
    onAnalysisComplete?.(updated);
    setTimeout(() => setIsRunningAnalysis(false), 1200);
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const text = chatInput;
    setChatInput('');
    setChatMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, sender: 'user', text, timestamp: new Date().toLocaleTimeString() },
    ]);
    setChatLoading(true);
    const reply = await sendChatMessage(text);
    setChatMessages((prev) => [...prev, reply]);
    setChatLoading(false);
  };

  const { evidence } = liveAnomaly;
  const isAnomalous = Math.abs(liveAnomaly.z_score) >= 3.0;
  const isDrop = liveAnomaly.pct_change < 0;

  return (
    <div className="flex flex-col gap-0 animate-fade-in">
      {/* ── Header panel ── */}
      <div className="card rounded-b-none border-b-0 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          {/* Left: title + badges */}
          <div className="flex items-start gap-3 min-w-0">
            <div className="p-2 rounded-lg bg-brand-50 border border-brand-200 shrink-0 mt-0.5">
              <BrainCircuit className="w-4 h-4 text-brand-600" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                {isAnomalous ? (
                  <span className="badge badge-red">
                    <AlertTriangle className="w-3 h-3" /> ANOMALY DETECTED
                  </span>
                ) : (
                  <span className="badge badge-green">
                    <CheckCircle2 className="w-3 h-3" /> NORMAL
                  </span>
                )}
                <span className="mono-pill">|Z| = {liveAnomaly.z_score}</span>
                <span className="mono-pill">{liveAnomaly.metric?.toUpperCase()}</span>
              </div>
              <h2 className="text-[15px] font-bold text-slate-900 leading-snug truncate">{liveAnomaly.title}</h2>
              <p className="text-[11px] text-slate-400 mt-0.5">{liveAnomaly.timestamp}</p>
            </div>
          </div>

          {/* Right: KPI pills */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="text-right">
              <p className="section-label">Baseline</p>
              <p className="text-[15px] font-bold text-slate-900 font-mono">${liveAnomaly.baseline_value.toLocaleString()}</p>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div className="text-right">
              <p className="section-label">Current</p>
              <p className={`text-[15px] font-bold font-mono ${isDrop ? 'text-red-600' : 'text-emerald-600'}`}>
                ${liveAnomaly.current_value.toLocaleString()}
              </p>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div className="text-right">
              <p className="section-label">Change</p>
              <p className={`text-[15px] font-bold font-mono flex items-center gap-1 ${isDrop ? 'text-red-600' : 'text-emerald-600'}`}>
                {isDrop ? <TrendingDown className="w-3.5 h-3.5" /> : <TrendingUp className="w-3.5 h-3.5" />}
                {liveAnomaly.pct_change}%
              </p>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div className="text-right px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200 min-w-[160px]">
              <p className="section-label flex items-center justify-end gap-1 text-emerald-700 font-semibold mb-1">
                <Zap className="w-3 h-3 text-emerald-600 animate-pulse" /> CH Latency
                <span className="font-mono text-[13px] font-bold text-emerald-700 ml-1">
                  {evidence?.execution_time_ms || 76} ms
                </span>
              </p>
              <div className="space-y-0.5">
                {CH_SPANS.map((span) => {
                  const totalMs = evidence?.execution_time_ms || 76;
                  const spanMs = Math.max(1, Math.round((totalMs * span.durationPct) / 80)); // CH spans = 80% of total
                  return (
                    <div key={span.name} className="flex items-center justify-between gap-2">
                      <span className="text-[9px] text-emerald-600 truncate max-w-[90px]">{span.label}</span>
                      <span className="font-mono text-[9px] font-bold text-emerald-700 shrink-0">{spanMs}ms</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Run Analysis Control Bar (GET) ── */}
      <div className="rounded-none border border-slate-200 border-b-0 border-t-0 px-4 py-2.5 bg-slate-50">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="section-label shrink-0">Metric</span>
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 text-[12px] font-semibold text-slate-800 shadow-sm uppercase">
              {liveAnomaly.metric || 'revenue'}
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="section-label shrink-0">From</span>
            <input
              type="datetime-local"
              step="1"
              value={windowStart}
              onChange={(e) => setWindowStart(e.target.value)}
              className="bg-white text-[11px] text-slate-700 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-300 font-mono shadow-sm"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <span className="section-label shrink-0">To</span>
            <input
              type="datetime-local"
              step="1"
              value={windowEnd}
              onChange={(e) => setWindowEnd(e.target.value)}
              min={windowStart}
              className="bg-white text-[11px] text-slate-700 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-300 font-mono shadow-sm"
            />
          </div>

          <button
            onClick={handleRunAnalysis}
            disabled={isRunningAnalysis || !windowStart || !windowEnd}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-semibold text-[12px] transition-all disabled:opacity-60 shrink-0 shadow-sm"
          >
            {isRunningAnalysis ? (
              <><Sparkles className="w-3.5 h-3.5 animate-spin" /> Fetching Analysis...</>
            ) : (
              <><Play className="w-3.5 h-3.5" /> Get Analysis</>
            )}
          </button>

          <button
            onClick={onOpenLangfuseTrace}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12px] font-medium transition-all shrink-0 ml-auto shadow-sm ${
              isTraceOpen
                ? 'bg-violet-600 text-white border-violet-500'
                : 'bg-white hover:bg-violet-50 border-violet-200 text-violet-700'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" /> Langfuse Traces
          </button>
        </div>
      </div>

      {/* ── Tab bar ── */}
      <div className="rounded-none border border-slate-200 border-b-0 border-t-0 flex items-center gap-0 px-1 bg-white">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3.5 py-2.5 text-[12px] font-medium border-b-2 transition-all ${
              activeTab === tab.id
                ? 'border-brand-500 text-brand-700'
                : 'border-transparent text-slate-400 hover:text-slate-700'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div className="card rounded-t-none p-4 space-y-4">

        {/* ── TAB: Overview ── */}
        {activeTab === 'overview' && (
          <div className="space-y-4 animate-slide-up">
            {/* Human-in-the-Loop controls */}
            <HumanLoopControls
              status={liveAnomaly.humanReview.status}
              reviewedAt={liveAnomaly.humanReview.reviewedAt}
              reviewedBy={liveAnomaly.humanReview.reviewedBy}
              hallucinationReason={liveAnomaly.humanReview.hallucinationReason}
              feedbackNote={liveAnomaly.humanReview.feedbackNote}
              onApprove={() => onApprove(liveAnomaly.id)}
              onFlagHallucination={(reason, feedback) => onFlagHallucination(liveAnomaly.id, reason, feedback)}
            />

            {/* Metric decomposition tree */}
            <MetricTreeVisualizer
              metric={liveAnomaly.metric}
              factorDecomp={evidence?.factor_decomposition}
              topSegments={evidence?.top_contributing_segments || []}
              ruledOut={evidence?.ruled_out || []}
            />

            {/* DeepSeek AI diagnosis */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-3.5 h-3.5 text-brand-500" />
                <h4 className="text-[12px] font-semibold text-slate-800">AI Diagnosis</h4>
                {/* Dynamic model pill — reads from actual llmMetrics */}
                <span className="mono-pill ml-auto">
                  {liveAnomaly.llmMetrics?.provider ?? 'DeepSeek'}
                  {' · '}
                  {liveAnomaly.llmMetrics?.model ?? (process.env.DEEPSEEK_MODEL || 'deepseek-chat')}
                  {' · Verbatim'}
                </span>
                {liveAnomaly.llmMetrics?.latencyMs != null && (
                  <span className="mono-pill text-amber-700 border-amber-200 bg-amber-50">
                    {liveAnomaly.llmMetrics.latencyMs}ms
                  </span>
                )}
              </div>
              <div className="text-[13px] text-slate-700 leading-relaxed bg-white border border-slate-200 rounded-lg p-4 prose prose-slate prose-sm max-w-none shadow-sm
                [&_strong]:text-slate-900 [&_strong]:font-semibold
                [&_em]:text-slate-500 [&_em]:italic
                [&_ul]:mt-2 [&_ul]:space-y-1 [&_ul]:list-disc [&_ul]:pl-4
                [&_ol]:mt-2 [&_ol]:space-y-1 [&_ol]:list-decimal [&_ol]:pl-4
                [&_li]:text-slate-700
                [&_code]:font-mono [&_code]:text-[11px] [&_code]:bg-slate-100 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-emerald-700
                [&_p]:mb-2 [&_p:last-child]:mb-0
                [&_h1]:text-[14px] [&_h1]:font-bold [&_h1]:text-slate-900 [&_h1]:mb-1
                [&_h2]:text-[13px] [&_h2]:font-semibold [&_h2]:text-slate-800 [&_h2]:mb-1
                [&_h3]:text-[12px] [&_h3]:font-semibold [&_h3]:text-slate-700 [&_h3]:mb-1
              ">
                <ReactMarkdown>{liveAnomaly.diagnosisText}</ReactMarkdown>
              </div>

              {/* LLM Metrics strip — dynamic, populated from backend response */}
              {liveAnomaly.llmMetrics && (
                <div className="mt-2 flex flex-wrap items-center gap-2 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mr-1">LLM Metrics</span>

                  <div className="flex items-center gap-1 px-2 py-1 rounded bg-violet-50 border border-violet-200">
                    <Zap className="w-3 h-3 text-violet-500" />
                    <span className="font-mono text-[11px] text-violet-700 font-semibold">
                      {liveAnomaly.llmMetrics.latencyMs}ms
                    </span>
                    <span className="text-[10px] text-violet-400 ml-0.5">latency</span>
                  </div>

                  <div className="flex items-center gap-1 px-2 py-1 rounded bg-blue-50 border border-blue-200">
                    <span className="text-[10px] text-blue-400">prompt</span>
                    <span className="font-mono text-[11px] text-blue-700 font-semibold">
                      {liveAnomaly.llmMetrics.promptTokens > 0
                        ? liveAnomaly.llmMetrics.promptTokens
                        : '—'}
                    </span>
                    <span className="text-[10px] text-blue-400">tok</span>
                  </div>

                  <div className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-50 border border-emerald-200">
                    <span className="text-[10px] text-emerald-400">completion</span>
                    <span className="font-mono text-[11px] text-emerald-700 font-semibold">
                      {liveAnomaly.llmMetrics.completionTokens > 0
                        ? liveAnomaly.llmMetrics.completionTokens
                        : '—'}
                    </span>
                    <span className="text-[10px] text-emerald-400">tok</span>
                  </div>

                  <div className="flex items-center gap-1 px-2 py-1 rounded bg-amber-50 border border-amber-200">
                    <span className="text-[10px] text-amber-500">total</span>
                    <span className="font-mono text-[11px] text-amber-700 font-semibold">
                      {liveAnomaly.llmMetrics.totalTokens > 0
                        ? liveAnomaly.llmMetrics.totalTokens
                        : '—'}
                    </span>
                    <span className="text-[10px] text-amber-400">tok</span>
                  </div>

                  <div className="ml-auto flex items-center gap-1 px-2 py-1 rounded bg-slate-100 border border-slate-200">
                    <span className="font-mono text-[11px] text-slate-600 font-semibold">
                      {liveAnomaly.llmMetrics.provider} / {liveAnomaly.llmMetrics.model}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB: Segments ── */}
        {activeTab === 'segments' && (
          <div className="space-y-4 animate-slide-up">
            {/* Top contributors */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5 text-brand-500" />
                  <h4 className="text-[12px] font-semibold text-slate-800">Top Contributing Segments</h4>
                </div>
                <span className="section-label">Share of Delta</span>
              </div>
              <div className="space-y-2">
                {(evidence?.top_contributing_segments || []).map((seg, idx) => {
                  const base = seg.baseline_metric ?? (seg as any).base_metric ?? 0;
                  const cur  = seg.current_metric  ?? (seg as any).current_m  ?? 0;
                  const pct  = seg.share_of_delta * 100;
                  return (
                    <div key={idx} className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
                      <div className="flex items-center justify-between text-[12px] mb-2">
                        <span className="font-semibold text-slate-800">
                          #{idx + 1} <span className="text-slate-400 font-normal">{seg.dimension}:</span>{' '}
                          <span className="text-brand-600">{seg.value}</span>
                        </span>
                        <span className="font-mono font-bold text-amber-600">{pct.toFixed(1)}%</span>
                      </div>
                      {/* Bar */}
                      <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden mb-2">
                        <div
                          className="bg-gradient-to-r from-amber-400 to-red-400 h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                        <span>Base: ${base.toLocaleString()}</span>
                        <span>Now: ${cur.toLocaleString()}</span>
                        <span className="text-red-500">Δ ${seg.segment_delta?.toLocaleString() ?? '—'}</span>
                      </div>
                    </div>
                  );
                })}
                {(!evidence?.top_contributing_segments || evidence.top_contributing_segments.length === 0) && (
                  <p className="text-[12px] text-slate-400 font-mono p-4">No contributing segments found for this window.</p>
                )}
              </div>
            </div>

            {/* Ruled-out dimensions */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                <h4 className="text-[12px] font-semibold text-slate-800">Ruled-Out Dimensions</h4>
                <span className="badge-green badge ml-auto">Cleared</span>
              </div>
              <div className="space-y-2">
                {(evidence?.ruled_out || []).map((item, idx) => (
                  <div key={idx} className="flex items-start gap-2.5 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-[12px]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-700 capitalize">{item.dimension?.replace(/_/g, ' ')}: </span>
                      <span className="text-slate-500">{item.reason}</span>
                    </div>
                  </div>
                ))}
                {(!evidence?.ruled_out || evidence.ruled_out.length === 0) && (
                  <p className="text-[12px] text-slate-400 p-4">No ruled-out factors recorded.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: Chat ── */}
        {activeTab === 'chat' && (
          <div className="flex flex-col gap-3 animate-slide-up">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-200">
              <MessageSquare className="w-3.5 h-3.5 text-brand-500" />
              <h4 className="text-[12px] font-semibold text-slate-800">ClickHouse MCP + DeepSeek Chat</h4>
              <span className="mono-pill ml-auto">POST /api/v1/chat</span>
            </div>

            <div className="space-y-3 min-h-[260px] max-h-[380px] overflow-y-auto pr-1">
              {chatMessages.map((msg) => (
                <div key={msg.id} className={`flex items-start gap-2.5 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs ${
                    msg.sender === 'user'
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-100 text-slate-500 border border-slate-200'
                  }`}>
                    {msg.sender === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                  </div>
                  <div className={`space-y-1 max-w-[82%] ${msg.sender === 'user' ? 'items-end' : ''}`}>
                    <div className={`px-3 py-2 rounded-xl text-[12px] leading-relaxed ${
                      msg.sender === 'user'
                        ? 'bg-brand-50 border border-brand-200 text-slate-800 rounded-tr-sm'
                        : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                    }`}>
                      {msg.text}
                    </div>
                    {msg.sqlQuery && (
                      <div className="p-2 rounded-lg bg-slate-900 border border-slate-700 text-[11px] font-mono text-emerald-400">
                        <span className="text-slate-500 block text-[10px] mb-1">// ClickHouse SQL</span>
                        {msg.sqlQuery}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex items-center gap-2 text-[11px] text-slate-400 p-2">
                  <Sparkles className="w-3.5 h-3.5 animate-spin text-brand-500" />
                  Querying ClickHouse MCP...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <form onSubmit={handleSendChat} className="flex items-center gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask a follow-up (e.g. Compare iOS 17 vs Android 14 fill rate)…"
                className="flex-1 bg-white text-[12px] text-slate-900 border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 placeholder:text-slate-400"
              />
              <button
                type="submit"
                disabled={!chatInput.trim() || chatLoading}
                className="px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-semibold text-[12px] transition-all disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
              >
                <Send className="w-3.5 h-3.5" /> Send
              </button>
            </form>
          </div>
        )}

        {/* ── TAB: Trace ── */}
        {activeTab === 'trace' && (
          <div className="space-y-4 animate-slide-up">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-200">
              <Code2 className="w-3.5 h-3.5 text-emerald-600" />
              <h4 className="text-[12px] font-semibold text-slate-800">Evidence JSON &amp; ClickHouse Trace</h4>
              <span className="mono-pill ml-auto">{evidence?.execution_time_ms ?? 0}ms</span>
              <button
                onClick={onOpenLangfuseTrace}
                className="btn-ghost py-1 px-2.5 text-[11px]"
              >
                <Terminal className="w-3 h-3" /> Langfuse Dashboard
              </button>
            </div>

            <p className="text-[12px] text-slate-500">
              Every number in this JSON was computed by ClickHouse SQL + the Go RCA engine. The DeepSeek narrator is
              constrained to use only values that appear verbatim in this payload.
            </p>

            <button
              onClick={() => setShowRawJson(!showRawJson)}
              className="flex items-center gap-2 text-[12px] text-slate-500 hover:text-slate-800 font-medium transition-colors"
            >
              {showRawJson ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              {showRawJson ? 'Collapse' : 'Expand'} Raw Evidence Payload
            </button>

            {showRawJson && (
              <pre className="p-4 rounded-lg bg-slate-900 border border-slate-700 font-mono text-[11px] text-emerald-400 overflow-x-auto max-h-96 leading-relaxed">
                {JSON.stringify(evidence, null, 2)}
              </pre>
            )}

            {/* Langfuse trace spans */}
            {liveAnomaly.langfuse && (
              <div>
                <p className="section-label mb-2">Langfuse Spans</p>
                <div className="space-y-1.5">
                  {Object.entries(liveAnomaly.langfuse).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex items-start gap-3 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-[12px]">
                      <span className="text-slate-400 font-mono text-[11px] shrink-0 mt-0.5">{key}</span>
                      <span className="text-slate-700 font-mono break-all">{JSON.stringify(val)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Prompt toggle to show side panel */}
            {!liveAnomaly.langfuse && (
              <div className="p-4 rounded-lg bg-violet-50 border border-violet-200 text-center">
                <p className="text-[12px] text-violet-700 mb-2 font-medium">Run an analysis to generate live Langfuse trace data</p>
                <button
                  onClick={onOpenLangfuseTrace}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white font-semibold text-[12px] transition-all"
                >
                  <Terminal className="w-3.5 h-3.5" /> Open Trace Panel
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
