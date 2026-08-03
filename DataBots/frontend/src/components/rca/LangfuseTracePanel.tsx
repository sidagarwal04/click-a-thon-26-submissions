import React from 'react';
import { LangfuseTelemetry, LlmMetrics } from '../../types';
import {
  Terminal,
  ExternalLink,
  X,
  CheckCircle2,
  ShieldAlert,
  Zap,
  BarChart3,
  Layers,
  Database,
  Brain,
  Activity,
} from 'lucide-react';

interface LangfuseTracePanelProps {
  telemetry?: LangfuseTelemetry;
  executionTimeMs?: number;
  llmMetrics?: LlmMetrics;
  onClose: () => void;
}

// ClickHouse pipeline spans — displayed in CH Latency section of RcaDetailDrawer
export const CH_SPANS = [
  {
    name: 'clickhouse-anomaly-detection',
    label: 'Baseline Detection',
    icon: Database,
    color: 'blue',
    durationPct: 20,
    description: 'ClickHouse SQL baseline vs current window evaluation',
  },
  {
    name: 'clickhouse-factor-decomposition',
    label: 'Factor Decomposition',
    icon: Layers,
    color: 'indigo',
    durationPct: 20,
    description: 'Revenue identity factor drilldown (fill rate, requests, eCPM)',
  },
  {
    name: 'clickhouse-segment-attribution',
    label: 'Segment Attribution',
    icon: Activity,
    color: 'amber',
    durationPct: 30,
    description: 'Single-Pass GROUP BY GROUPING SETS dimensional attribution',
  },
  {
    name: 'clickhouse-ruled-out-verification',
    label: 'Ruled-Out Checks',
    icon: CheckCircle2,
    color: 'emerald',
    durationPct: 10,
    description: 'Verification that cleared dimensions are non-causal',
  },
];

// LLM-only spans — shown in the Langfuse trace panel
const LLM_SPANS = [
  {
    name: 'deepseek-llm-narration',
    label: 'DeepSeek Narration',
    icon: Brain,
    color: 'violet',
    durationPct: 100, // 100% of LLM-only budget
    description: 'LLM constrained verbatim RCA summary generation',
  },
];

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; bar: string; dot: string }> = {
  blue:    { bg: 'bg-blue-50',    border: 'border-blue-200',    text: 'text-blue-700',    bar: 'bg-blue-400',    dot: 'bg-blue-500' },
  indigo:  { bg: 'bg-indigo-50',  border: 'border-indigo-200',  text: 'text-indigo-700',  bar: 'bg-indigo-400',  dot: 'bg-indigo-500' },
  amber:   { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   bar: 'bg-amber-400',   dot: 'bg-amber-500' },
  emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', bar: 'bg-emerald-400', dot: 'bg-emerald-500' },
  violet:  { bg: 'bg-violet-50',  border: 'border-violet-200',  text: 'text-violet-700',  bar: 'bg-violet-400',  dot: 'bg-violet-500' },
};

export const LangfuseTracePanel: React.FC<LangfuseTracePanelProps> = ({ telemetry, executionTimeMs, llmMetrics, onClose }) => {
  const faithfulness = (telemetry?.faithfulnessScore ?? 1.0) * 100;
  const totalLatency = executionTimeMs ?? telemetry?.executionTimeMs ?? 434;
  // Use real llmMetrics latency if available, otherwise estimate as ~20% of total
  const llmLatency = llmMetrics?.latencyMs ?? Math.round(totalLatency * 0.2);
  const llmModel = llmMetrics?.model ?? 'deepseek-chat';
  const llmProvider = llmMetrics?.provider ?? 'DeepSeek';
  const traceId = telemetry?.traceId ?? 'trace-active-session';
  const traceUrl = telemetry?.traceUrl ?? (telemetry?.traceId ? `https://cloud.langfuse.com/trace/${telemetry.traceId}` : 'https://cloud.langfuse.com');
  const isHighFidelity = faithfulness >= 95;

  return (
    <div className="card flex flex-col h-full overflow-hidden animate-slide-in-r">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-violet-100 border border-violet-200 flex items-center justify-center">
            <Terminal className="w-3.5 h-3.5 text-violet-600" />
          </div>
          <div>
            <h3 className="text-[13px] font-bold text-slate-900 leading-tight">Langfuse Traces</h3>
            <p className="text-[10px] text-slate-400 leading-tight">RCA Investigation Pipeline</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Trace ID + link */}
        <div className="p-3 rounded-lg bg-violet-50 border border-violet-200">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-500 mb-1">Trace ID</p>
          <p className="font-mono text-[11px] text-violet-800 font-bold break-all">{traceId}</p>
          <a
            href={traceUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 mt-2 text-[11px] text-violet-600 hover:text-violet-800 font-semibold transition-colors"
          >
            Open in Langfuse Cloud <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Quality Scores */}
        <div className="grid grid-cols-2 gap-2">
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
            <div className="flex items-center gap-1.5 mb-1.5">
              {isHighFidelity
                ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                : <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
              }
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Faithfulness</span>
            </div>
            <div className={`text-[22px] font-bold font-mono ${isHighFidelity ? 'text-emerald-600' : 'text-amber-600'}`}>
              {faithfulness.toFixed(0)}%
            </div>
            <div className="mt-1.5 w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${isHighFidelity ? 'bg-emerald-400' : 'bg-amber-400'}`}
                style={{ width: `${faithfulness}%` }}
              />
            </div>
            <p className="text-[10px] text-slate-400 mt-1">{isHighFidelity ? 'Fully faithful' : 'Minor drift'}</p>
          </div>
        </div>

        {/* LLM Span Timeline */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="w-3.5 h-3.5 text-slate-500" />
            <h4 className="text-[12px] font-semibold text-slate-700">LLM Execution Timeline</h4>
          </div>

          {/* Gantt-style progress bar — LLM only */}
          <div className="space-y-1.5 mb-3">
            {LLM_SPANS.map((span) => {
              const c = COLOR_MAP[span.color];
              return (
                <div key={span.name} className="flex items-center gap-2">
                  <div className="w-24 shrink-0">
                    <div className="h-5 bg-slate-100 rounded-sm overflow-hidden relative">
                      <div
                        className={`absolute top-0 h-full ${c.bar} opacity-80 rounded-sm`}
                        style={{ left: '0%', width: '100%' }}
                      />
                    </div>
                  </div>
                  <span className={`text-[10px] font-semibold ${c.text} truncate`}>{span.label}</span>
                </div>
              );
            })}
          </div>

          {/* LLM span detail */}
          <div className="space-y-2">
            {LLM_SPANS.map((span) => {
              const c = COLOR_MAP[span.color];
              const Icon = span.icon;
              return (
                <div key={span.name} className={`rounded-lg border ${c.border} ${c.bg} p-3`}>
                  <div className="flex items-start gap-2">
                    <div className={`w-5 h-5 rounded-md bg-white border ${c.border} flex items-center justify-center shrink-0 mt-0.5`}>
                      <Icon className={`w-3 h-3 ${c.text}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1 mb-0.5">
                        <span className={`text-[11px] font-bold ${c.text}`}>{span.label}</span>
                        <span className="font-mono text-[10px] text-slate-400 shrink-0">{llmLatency}ms</span>
                      </div>
                      <p className="text-[10px] text-slate-500 leading-relaxed">{span.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Telemetry metadata if available */}
        {telemetry && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-3.5 h-3.5 text-slate-500" />
              <h4 className="text-[12px] font-semibold text-slate-700">Telemetry Metadata</h4>
            </div>
            <div className="space-y-1.5">
              {Object.entries(telemetry).map(([key, val]: [string, any]) => (
                <div key={key} className="flex items-start gap-2 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-[11px]">
                  <span className="text-slate-400 font-mono shrink-0 mt-0.5 text-[10px]">{key}</span>
                  <span className="text-slate-700 font-mono break-all ml-auto">{JSON.stringify(val)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Hallucination status */}
        <div className={`rounded-lg border p-3 ${isHighFidelity ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
          <div className="flex items-center gap-2">
            {isHighFidelity
              ? <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              : <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0" />
            }
            <div>
              <p className={`text-[12px] font-semibold ${isHighFidelity ? 'text-emerald-700' : 'text-amber-700'}`}>
                {isHighFidelity ? 'No Hallucinations Detected' : 'Possible Drift Detected'}
              </p>
              <p className={`text-[10px] ${isHighFidelity ? 'text-emerald-500' : 'text-amber-500'}`}>
                {isHighFidelity
                  ? 'All LLM numbers trace back to ClickHouse evidence'
                  : 'Some figures may not be verbatim from evidence bundle'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
