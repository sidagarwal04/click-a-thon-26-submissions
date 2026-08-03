import { useEffect, useState } from "react";
import { getTrace, type TraceStep, type TraceView } from "../api";

const CloseIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

// Phase names are the trace's vocabulary; these are the customer's.
function stepLabel(phase: string): string {
  if (phase.startsWith("depth-")) {
    const [depth, dim] = phase.split(":");
    return dim && dim !== "stop" ? `Drill ${depth.replace("depth-", "L")} · ${dim}` : "Drill · stop";
  }
  const labels: Record<string, string> = {
    detect: "Detect",
    decompose: "Attribute",
    drilldown: "Localize",
    "ruled-out": "Rule out",
  };
  return labels[phase] ?? (phase.startsWith("narrate") ? "Narrate" : phase);
}

function ms(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${value}ms`;
}

function Step({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const stopped = step.verdict?.decision === "stop";

  return (
    <li className={`trace-step ${stopped ? "is-stop" : ""}`}>
      <div className="ts-head">
        <span className="ts-label">{stepLabel(step.phase)}</span>
        <span className="ts-ms mono">{ms(step.ms)}</span>
      </div>
      <p className="ts-headline">{step.headline}</p>
      {step.queries.length > 0 && (
        <>
          <button className="ts-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? "Hide" : "Show"} {step.queries.length} quer{step.queries.length === 1 ? "y" : "ies"}
          </button>
          {open && (
            <div className="ts-queries">
              {step.queries.map((q, i) => (
                <div key={`${q.name}-${i}`} className="ts-query">
                  <div className="ts-query-head">
                    <span className="mono">{q.name}</span>
                    <span className="ts-ms mono">{ms(q.ms)}</span>
                  </div>
                  <pre className="ts-sql">{q.sql}</pre>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </li>
  );
}

// Slide-over showing the Langfuse trace as the investigation's story: one step per phase with
// a plain-language headline, its duration, and the SQL behind it. The raw Langfuse UI is
// comprehensive but developer-facing, so it stays one link away in the footer.
export function TraceDrawer({
  investigationId,
  traceUrl,
  open,
  onClose,
}: {
  investigationId: string | null;
  traceUrl?: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [view, setView] = useState<TraceView | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch lazily, and refetch when the drawer is reopened on a different investigation.
  useEffect(() => {
    if (!open || !investigationId) return;
    setLoading(true);
    getTrace(investigationId).then((v) => {
      setView(v);
      setLoading(false);
    });
  }, [open, investigationId]);

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [onClose]);

  const scores = view?.scores ?? {};

  return (
    <>
      <div className={`trace-scrim ${open ? "open" : ""}`} onClick={onClose} aria-hidden={!open} />
      <aside className={`trace-drawer ${open ? "open" : ""}`} role="dialog" aria-label="How this was investigated">
        <header className="trace-head">
          <div>
            <span className="eyebrow">How this was investigated</span>
            {view?.available && (
              <div className="trace-sub">
                <span className="mono">{ms(view.total_ms ?? 0)}</span> · {view.steps?.length ?? 0} steps
                {Object.entries(scores).map(([name, value]) => (
                  <span key={name} className="trace-score mono">
                    {name.replace(/_/g, " ")} {typeof value === "number" ? value.toFixed(1) : value}
                  </span>
                ))}
              </div>
            )}
          </div>
          <button className="dock-icon" onClick={onClose} aria-label="Close">{CloseIcon}</button>
        </header>

        <div className="trace-body">
          {loading && <div className="trace-empty">Loading trace…</div>}
          {!loading && view && !view.available && (
            <div className="trace-empty">Trace unavailable — {view.reason}</div>
          )}
          {!loading && view?.available && (
            <ol className="trace-steps">
              {view.steps?.map((step, i) => <Step key={`${step.phase}-${i}`} step={step} />)}
            </ol>
          )}
        </div>

        {traceUrl && (
          <footer className="trace-foot">
            <a className="ghost-btn" href={traceUrl} target="_blank" rel="noreferrer">
              Open raw trace ↗
            </a>
          </footer>
        )}
      </aside>
    </>
  );
}
