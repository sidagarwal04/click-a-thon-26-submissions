import { AlertCircle, CheckCircle2, Clock3, Search, Workflow } from "lucide-react";
import { compactDuration, relativeTime, titleCase } from "../format";
import type { RunSummary } from "../types";

interface RunListProps {
  runs: RunSummary[];
  selectedId: string | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (id: string) => void;
}

export function RunList({ runs, selectedId, query, onQueryChange, onSelect }: RunListProps) {
  return (
    <aside className="run-panel">
      <div className="run-panel__header">
        <div><span className="eyebrow">Trace history</span><h2>Runs <span>{runs.length}</span></h2></div>
        <div className="search-box"><Search size={15} /><input value={query} onChange={(e) => onQueryChange(e.target.value)} placeholder="Search runs" aria-label="Search runs" /></div>
      </div>
      <div className="run-list">
        {runs.length === 0 && <div className="list-empty">No matching runs.</div>}
        {runs.map((run) => {
          const failed = run.status.toLowerCase().includes("error") || run.error_count > 0;
          return (
            <button className={`run-row ${run.id === selectedId ? "run-row--selected" : ""}`} key={run.id} onClick={() => onSelect(run.id)}>
              <span className={`status-icon ${failed ? "status-icon--error" : "status-icon--success"}`}>{failed ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}</span>
              <span className="run-row__body">
                <span className="run-row__top"><strong>{run.feature || titleCase(run.name)}</strong><time>{relativeTime(run.timestamp)}</time></span>
                <span className="run-row__meta"><span><Workflow size={12} />{run.observation_count} steps</span><span><Clock3 size={12} />{compactDuration(run.latency)}</span></span>
                <span className="run-id">{run.id.slice(0, 12)}</span>
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
