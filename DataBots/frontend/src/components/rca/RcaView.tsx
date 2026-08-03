import React, { useState } from 'react';
import { AnomalyIncident } from '../../types';
import { RcaDetailDrawer } from './RcaDetailDrawer';
import { LangfuseTracePanel } from './LangfuseTracePanel';
import { BrainCircuit, RefreshCw, Play } from 'lucide-react';

interface RcaViewProps {
  anomalies: AnomalyIncident[];
  onApprove: (id: string) => void;
  onFlagHallucination: (id: string, reason: string, feedback: string) => void;
  onUpdateAnomaly?: (updated: AnomalyIncident) => void;
}

export const RcaView: React.FC<RcaViewProps> = ({ anomalies, onApprove, onFlagHallucination, onUpdateAnomaly }) => {
  const [showTracePanel, setShowTracePanel] = useState(false);
  const [isDemoReplaying, setIsDemoReplaying] = useState(false);
  const [demoStep, setDemoStep] = useState<number | null>(null);
  // Track the most recent analysed anomaly so the trace panel stays in sync
  const [liveAnomaly, setLiveAnomaly] = useState<AnomalyIncident | undefined>(anomalies[0]);

  // Keep liveAnomaly in sync when the prop changes (e.g. initial load or external update)
  React.useEffect(() => {
    if (anomalies.length > 0) {
      setLiveAnomaly((current) => {
        if (!current) return anomalies[0];
        const match = anomalies.find((a) => a.id === current.id);
        return match || current;
      });
    }
  }, [anomalies]);

  const selectedAnomaly = liveAnomaly ?? anomalies[0];

  const handleAnalysisComplete = (updated: AnomalyIncident) => {
    setLiveAnomaly(updated);
    onUpdateAnomaly?.(updated);
  };

  const handleReplayDemo = () => {
    setIsDemoReplaying(true);
    setDemoStep(1);
    setTimeout(() => setDemoStep(2), 1200);
    setTimeout(() => setDemoStep(3), 2400);
    setTimeout(() => {
      setDemoStep(4);
      setTimeout(() => { setIsDemoReplaying(false); setDemoStep(null); }, 2000);
    }, 3600);
  };

  const llmModel = selectedAnomaly?.llmMetrics?.model ?? 'deepseek-chat';
  const llmProvider = selectedAnomaly?.llmMetrics?.provider ?? 'DeepSeek';
  const llmLatency = selectedAnomaly?.llmMetrics?.latencyMs;

  const DEMO_STEPS = [
    { label: 'Anomaly Triggered', sub: '|Z| ≥ 3.0', color: 'amber' },
    { label: 'ClickHouse Fan-out', sub: 'SQL Parallel Queries', color: 'blue' },
    { label: 'Metric Tree Eval', sub: 'Contribution Scoring', color: 'red' },
    {
      label: `${llmProvider} Narration`,
      sub: `${llmModel}${llmLatency != null ? ` · ${llmLatency}ms` : ''} · LLM constrained verbatim`,
      color: 'green',
    },
  ];

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-brand-50 border border-brand-200">
            <BrainCircuit className="w-4 h-4 text-brand-600" />
          </div>
          <div>
            <h2 className="text-[14px] font-bold text-slate-900 leading-tight">Root Cause Analysis Workbench</h2>
            <p className="text-[11px] text-slate-400 leading-tight">ClickHouse · Go Worker Pool · {llmProvider} {llmModel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Demo walkthrough */}
          <button
            onClick={handleReplayDemo}
            disabled={isDemoReplaying}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-600 hover:text-slate-900 border border-slate-200 text-[12px] font-medium transition-all disabled:opacity-50 shadow-sm"
          >
            {isDemoReplaying
              ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              : <Play className="w-3.5 h-3.5" />
            }
            Demo Walkthrough
          </button>
        </div>
      </div>

      {/* Demo walkthrough progress */}
      {isDemoReplaying && (
        <div className="card px-4 py-3 animate-fade-in shrink-0">
          <div className="flex items-center justify-between mb-2.5">
            <span className="text-[12px] font-semibold text-slate-700">Demo Sequence Running</span>
            <span className="mono-pill">Step {demoStep} / 4</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {DEMO_STEPS.map((step, i) => {
              const active = demoStep !== null && demoStep > i;
              return (
                <div
                  key={i}
                  className={`px-3 py-2 rounded-lg border text-[11px] transition-all duration-300 ${
                    active
                      ? step.color === 'amber' ? 'bg-amber-50 border-amber-200 text-amber-700'
                        : step.color === 'blue'  ? 'bg-blue-50 border-blue-200 text-blue-700'
                        : step.color === 'red'   ? 'bg-red-50 border-red-200 text-red-700'
                        : 'bg-emerald-50 border-emerald-200 text-emerald-700'
                      : 'bg-slate-50 border-slate-200 text-slate-400'
                  }`}
                >
                  <div className="font-semibold">{step.label}</div>
                  <div className="text-[10px] opacity-70 mt-0.5">{step.sub}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Workbench Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
        {/* RCA Analysis Workbench (GET & SET) */}
        <div className={`${showTracePanel ? 'lg:col-span-9' : 'lg:col-span-12'} min-h-0 overflow-y-auto`}>
          {selectedAnomaly ? (
          <RcaDetailDrawer
              anomaly={selectedAnomaly}
              onApprove={onApprove}
              onFlagHallucination={onFlagHallucination}
              onOpenLangfuseTrace={() => setShowTracePanel((v) => !v)}
              onOpenChatAgent={() => {}}
              onAnalysisComplete={handleAnalysisComplete}
              isTraceOpen={showTracePanel}
            />
          ) : (
            <div className="card p-16 text-center text-[13px] text-slate-400">
              Select metric and window above, then click "Get Analysis".
            </div>
          )}
        </div>

        {/* Langfuse Trace Panel — inline side panel when open */}
        {showTracePanel && (
          <div className="lg:col-span-3 min-h-0 overflow-y-auto">
            <LangfuseTracePanel
              telemetry={selectedAnomaly?.langfuse}
              executionTimeMs={selectedAnomaly?.evidence?.execution_time_ms}
              llmMetrics={selectedAnomaly?.llmMetrics}
              onClose={() => setShowTracePanel(false)}
            />
          </div>
        )}
      </div>
    </div>
  );
};
