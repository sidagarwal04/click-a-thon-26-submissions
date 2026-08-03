import { Bot, Braces, ChevronDown, CircleDot, Database, TerminalSquare } from "lucide-react";
import { useState } from "react";
import { compactDuration, titleCase } from "../format";
import type { Observation } from "../types";
import { JsonView } from "./JsonView";

function StepIcon({ observation }: { observation: Observation }) {
  const name = observation.name.toLowerCase();
  if (observation.type === "AGENT") return <Bot size={15} />;
  if (name.includes("sql") || name.includes("ddl") || name.includes("clickhouse") || name.includes("ingest")) return <Database size={15} />;
  if (name.includes("schema") || name.includes("profile")) return <Braces size={15} />;
  return <TerminalSquare size={15} />;
}

function ObservationRow({ observation, totalLatency }: { observation: Observation; totalLatency: number }) {
  const [open, setOpen] = useState(false);
  const width = Math.max(0.8, ((observation.latency ?? 0) / Math.max(totalLatency, 0.001)) * 100);
  const left = Math.min(99, (observation.offset_ms / Math.max(totalLatency * 1000, 1)) * 100);
  const hasDetails = observation.input != null || observation.output != null || Object.keys(observation.metadata).length > 0 || observation.status_message;

  return (
    <article className={`step ${open ? "step--open" : ""}`}>
      <button className="step__summary" onClick={() => hasDetails && setOpen(!open)} aria-expanded={open}>
        <span className={`step__icon step__icon--${observation.type.toLowerCase()}`}><StepIcon observation={observation} /></span>
        <span className="step__identity"><strong>{titleCase(observation.name)}</strong><span><span className="type-label">{observation.type}</span>{observation.model && <span>{observation.model}</span>}</span></span>
        <span className="waterfall" aria-label={`Started ${observation.offset_ms} milliseconds into run`}><i style={{ left: `${left}%`, width: `${Math.min(width, 100 - left)}%` }} /></span>
        <span className="step__duration">{compactDuration(observation.latency)}</span>
        <ChevronDown className="step__chevron" size={16} />
      </button>
      {open && (
        <div className="step__detail">
          {observation.status_message && <div className="error-callout"><CircleDot size={14} />{observation.status_message}</div>}
          <div className="detail-grid">
            <section><h4>Input</h4><JsonView value={observation.input} /></section>
            <section><h4>Output</h4><JsonView value={observation.output} /></section>
          </div>
          <div className="detail-grid detail-grid--secondary">
            <section><h4>Metadata</h4><JsonView value={observation.metadata} /></section>
            <section><h4>Usage</h4><JsonView value={observation.usage} /></section>
          </div>
        </div>
      )}
    </article>
  );
}

export function Timeline({ observations, latency }: { observations: Observation[]; latency: number | null }) {
  const roots = observations.filter((item) => item.parent_observation_id == null);
  const rootIds = new Set(roots.map((item) => item.id));
  const visible = observations.filter((item) => !rootIds.has(item.id));
  return (
    <div className="timeline">
      <div className="timeline__scale"><span>START</span><i /><span>{compactDuration(latency)}</span></div>
      {visible.map((observation) => <ObservationRow key={observation.id} observation={observation} totalLatency={latency ?? 0} />)}
    </div>
  );
}
