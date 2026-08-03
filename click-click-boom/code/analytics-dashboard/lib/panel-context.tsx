'use client';
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

// The same right panel serves four purposes: running a NEW ingestion (mode
// 'new', the original behavior), reviewing how a PAST spec was ingested
// (mode 'history', driven by historySpec), running the analytics agent
// against an already-executed spec (mode 'analytics', driven by
// analyticsSpec), and reviewing the trace behind one PAST insight (mode
// 'history' again, driven by historyInsight instead of historySpec — a spec
// can have multiple insights now that analytics is an explicit, re-runnable
// step, so "this spec's trace" isn't specific enough once you're looking at
// one particular insight) — one component, one visual language, instead of
// separate pages per action. See components/agent-panel.tsx's history block.
type PanelMode = 'new' | 'history' | 'analytics';

export interface HistoryInsightTarget {
  insightId: string;
  title?: string;
  specName?: string;
}

interface PanelCtx {
  isOpen: boolean;
  mode: PanelMode;
  historySpec: string | null;
  historyInsight: HistoryInsightTarget | null;
  analyticsSpec: string | null;
  open: () => void;
  close: () => void;
}

const Ctx = createContext<PanelCtx>({
  isOpen: false, mode: 'new', historySpec: null, historyInsight: null, analyticsSpec: null,
  open: () => {}, close: () => {},
});

export function PanelProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<PanelMode>('new');
  const [historySpec, setHistorySpec] = useState<string | null>(null);
  const [historyInsight, setHistoryInsight] = useState<HistoryInsightTarget | null>(null);
  const [analyticsSpec, setAnalyticsSpec] = useState<string | null>(null);

  const open  = useCallback(() => { setMode('new'); setHistorySpec(null); setHistoryInsight(null); setIsOpen(true); }, []);
  const close = useCallback(() => setIsOpen(false), []);

  // Allow any component to open the panel via DOM events (keeps callers from
  // needing to thread the panel context through every button that opens it)
  useEffect(() => {
    const onNew = () => { setMode('new'); setHistorySpec(null); setHistoryInsight(null); setIsOpen(true); };
    const onHistory = (e: Event) => {
      const specName = (e as CustomEvent<string>).detail;
      setMode('history'); setHistorySpec(specName); setHistoryInsight(null); setIsOpen(true);
    };
    const onInsightTrace = (e: Event) => {
      const target = (e as CustomEvent<HistoryInsightTarget>).detail;
      setMode('history'); setHistoryInsight(target); setHistorySpec(null); setIsOpen(true);
    };
    const onAnalytics = (e: Event) => {
      // detail is null when opened from the Insights page's bare "Create
      // Insight" button (no spec chosen yet — the panel shows a picker);
      // a specific spec name when opened pre-targeted at one.
      const specName = (e as CustomEvent<string | null>).detail;
      setMode('analytics'); setAnalyticsSpec(specName ?? null); setIsOpen(true);
    };
    window.addEventListener('open-agent-panel', onNew);
    window.addEventListener('open-agent-panel-history', onHistory as EventListener);
    window.addEventListener('open-agent-panel-insight-trace', onInsightTrace as EventListener);
    window.addEventListener('open-agent-panel-analytics', onAnalytics as EventListener);
    return () => {
      window.removeEventListener('open-agent-panel', onNew);
      window.removeEventListener('open-agent-panel-history', onHistory as EventListener);
      window.removeEventListener('open-agent-panel-insight-trace', onInsightTrace as EventListener);
      window.removeEventListener('open-agent-panel-analytics', onAnalytics as EventListener);
    };
  }, []);

  return (
    <Ctx.Provider value={{ isOpen, mode, historySpec, historyInsight, analyticsSpec, open, close }}>
      {children}
    </Ctx.Provider>
  );
}

export const usePanelCtx = () => useContext(Ctx);

// Call this from anywhere to open the panel in "run a new ingestion" mode
export function openAgentPanel() {
  window.dispatchEvent(new Event('open-agent-panel'));
}

// Call this to open the panel showing how `specName` was ingested
export function openSpecHistory(specName: string) {
  window.dispatchEvent(new CustomEvent('open-agent-panel-history', { detail: specName }));
}

// Call this to open the panel showing one specific insight's own analytics
// trace (tool calls, reasoning, the InsightWidget) — distinct from
// openSpecHistory since a spec can have several insights, each with its own
// trace, and this targets exactly one of them.
export function openInsightTrace(target: HistoryInsightTarget) {
  window.dispatchEvent(new CustomEvent('open-agent-panel-insight-trace', { detail: target }));
}

// Call this to open the panel in "run the analytics agent" mode. Pass a
// specName to pre-target a specific (already-executed) spec, or omit it to
// show the picker.
export function openAnalyticsPanel(specName?: string) {
  window.dispatchEvent(new CustomEvent('open-agent-panel-analytics', { detail: specName ?? null }));
}
