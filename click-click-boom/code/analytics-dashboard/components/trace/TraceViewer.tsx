'use client';
import { useState } from 'react';
import { Brain, Wrench, ShieldCheck, BookMarked, LineChart, Loader2, ChevronRight, ChevronDown, Rocket, BadgeCheck } from 'lucide-react';
import type { AgentEvent } from './types';
import { getEventFamily, cleanToolName, elapsed } from './utils';
import { SqlWidget } from './widgets/SqlWidget';
import { PythonWidget } from './widgets/PythonWidget';
import { SchemaWidget, TablesWidget } from './widgets/SchemaWidget';
import { ContextLookupWidget, ContextIndexWidget } from './widgets/ContextWidget';
import { SkillFileWidget, SkillListWidget } from './widgets/SkillWidget';
import { GenerationWidget } from './widgets/GenerationWidget';
import { ProposalWidget, ReviewWidget, InsightWidget, ApprovedWidget, ExecutionWidget, ContextUpdateWidget } from './widgets/ProposalReviewWidget';

// Only thinking (reasoning/generation), tool calls, and the three
// deterministic pipeline-outcome summaries (approved/execution/context_update
// -- see tracing/langfuse_wrapper.py's _step_kind docstring for why those
// used to be invisible) are shown here — the pipeline's own span/trace/
// plain-log bookkeeping events are real but not useful to a reader watching
// the agent work, so they're dropped rather than exposed behind a filter
// toggle.
const VISIBLE_KINDS = new Set(['reasoning', 'generation', 'tool_call', 'approved', 'execution', 'context_update']);

// ── Route event to correct widget ─────────────────────────────────────────────

// Live per-turn chain-of-thought chunk (kind="reasoning", raw text in
// `output`) -- distinct from a "generation" event's model_reasoning field
// (the FINAL turn's reasoning, attached alongside the agent's structured
// output). Same whisper visual language as GenerationWidget's reasoning
// block, but standalone since these arrive as their own live events.
function ThinkingWidget({ event }: { event: AgentEvent }) {
  const text = typeof event.output === 'string' ? event.output : '';
  if (!text.trim()) return null;
  return (
    <div className="rounded-r-lg overflow-hidden my-1" style={{ borderLeft: '2px solid #c4b5fd', backgroundColor: '#faf7ff' }}>
      <div className="px-3 pt-2 pb-1.5">
        <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest" style={{ color: '#8b5cf6' }}>
          <Brain className="h-2.5 w-2.5" /> thinking
        </span>
        <p className="mt-1 text-[11.5px] leading-relaxed whitespace-pre-wrap font-sans" style={{ color: '#6d28d9', opacity: 0.85 }}>
          {text.trim()}
        </p>
      </div>
    </div>
  );
}

function EventWidget({ event }: { event: AgentEvent }) {
  if (event.kind === 'reasoning') return <ThinkingWidget event={event} />;
  // Exactly what flows between the proposer and reviewer deserves real
  // structure, not the generic JSON-dump treatment every other "generation"
  // event gets — pipeline.py's step names are exactly "propose_generation"/
  // "review_generation" (see orchestrator/pipeline.py's _propose/_review).
  if (event.step === 'propose_generation') return <ProposalWidget event={event} />;
  if (event.step === 'review_generation')  return <ReviewWidget event={event} />;
  if (event.step === 'analytics_generation') return <InsightWidget event={event} />;
  if (event.step === 'approved')         return <ApprovedWidget event={event} />;
  if (event.step === 'executed')         return <ExecutionWidget event={event} />;
  if (event.step === 'context_updated')  return <ContextUpdateWidget event={event} />;

  const family = getEventFamily(event);
  const clean  = cleanToolName(event.step);

  switch (family) {
    case 'sql_query':
      return <SqlWidget step={clean} input={event.input} output={event.output} />;
    case 'schema':
      return <SchemaWidget step={clean} input={event.input} output={event.output} />;
    case 'tables':
      return <TablesWidget step={clean} input={event.input} output={event.output} />;
    case 'context_lookup':
      return <ContextLookupWidget step={clean} input={event.input} output={event.output} />;
    case 'context_index':
      return <ContextIndexWidget step={clean} output={event.output} />;
    case 'skill_file':
      return <SkillFileWidget step={clean} input={event.input} output={event.output} />;
    case 'skill_list':
      return <SkillListWidget step={clean} input={event.input} output={event.output} />;
    case 'python':
      return <PythonWidget step={clean} input={event.input} output={event.output} />;
    case 'generation':
      return <GenerationWidget event={event} />;
    default:
      // Generic log / span / other — simple one-liner
      return (
        <div className="flex items-center gap-2 py-1.5 px-2 text-xs rounded"
          style={{ color: '#9c9088' }}>
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: '#d4cfca' }} />
          <span className="font-mono">{event.step}</span>
          <span className="ml-auto text-[10px]">{elapsed(event.ts)}</span>
        </div>
      );
  }
}

// ── Phase grouping ───────────────────────────────────────────────────────────
// Every step name is prefixed with which agent call produced it -- pipeline.py
// calls _call_json_agent(..., "propose"/"review"/"chronicle", ...) and
// analytics_agent.py calls it with "analytics"; sub-steps are
// "{step}_reasoning[turnN]"/"{step}_tool[i]_{name}"/"{step}_generation". That
// prefix is the real phase boundary — surfacing it (with which revision
// attempt, since propose/review repeat on rework) is what actually answers
// "which agent is doing this right now."
type PhaseIcon = React.ComponentType<{ className?: string; style?: React.CSSProperties }>;

const PHASE_META: Record<string, { label: string; icon: PhaseIcon; accent: string }> = {
  propose:    { label: 'Instrumentation Agent (Proposal)',      icon: Wrench,      accent: '#d97706' },
  review:     { label: 'Context Agent (Review)',                icon: ShieldCheck, accent: '#2563eb' },
  approved:   { label: 'Context Agent (Approved)',              icon: BadgeCheck,  accent: '#0d9488' },
  executed:   { label: 'Instrumentation Agent (Execute)',       icon: Rocket,      accent: '#0891b2' },
  chronicle:  { label: 'Context Agent (Update Context)',        icon: BookMarked,  accent: '#7c3aed' },
  analytics:  { label: 'Analytics Agent',                       icon: LineChart,   accent: '#16a34a' },
};

function derivePhaseKey(step: string): string {
  // The chronicler's OWN reasoning/tool-call turn is step-prefixed
  // "chronicle_..." (matches naturally below), but the deterministic
  // "context_updated" summary that follows it -- the sections it actually
  // wrote -- has a step name that doesn't share that prefix. Force it into
  // the SAME phase group so it reads as "the chronicler worked, and here's
  // what it produced", not a disconnected fifth section.
  if (step === 'context_updated') return 'chronicle';
  return step.match(/^[a-zA-Z]+/)?.[0] ?? 'pipeline';
}

interface PhaseGroup { key: string; occurrence: number; events: AgentEvent[] }

// Groups by CONSECUTIVE runs of the same phase, not by phase identity alone —
// a rework loop revisits "propose" and "review" multiple times, and each
// pass should read as its own section in execution order, not get merged
// with an earlier attempt.
function groupByPhase(events: AgentEvent[]): PhaseGroup[] {
  const groups: PhaseGroup[] = [];
  const occurrenceCounts: Record<string, number> = {};
  let current: PhaseGroup | null = null;
  for (const ev of events) {
    const key = derivePhaseKey(ev.step);
    if (!current || current.key !== key) {
      occurrenceCounts[key] = (occurrenceCounts[key] ?? 0) + 1;
      current = { key, occurrence: occurrenceCounts[key], events: [] };
      groups.push(current);
    }
    current.events.push(ev);
  }
  return groups;
}

// Tool-call/generation/reasoning count -- what "expand to see N things" means
// for this group, since a thinking event isn't a tool call but still counts
// as something the reader would want a heads-up about.
function phaseCounts(group: PhaseGroup): { tools: number; total: number } {
  return {
    tools: group.events.filter(e => e.kind === 'tool_call').length,
    total: group.events.length,
  };
}

function PhaseSection({ group, isLive, defaultOpen }: { group: PhaseGroup; isLive: boolean; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = PHASE_META[group.key] ?? { label: group.key, icon: Wrench, accent: '#6b7280' };
  const Icon = meta.icon;
  const { tools, total } = phaseCounts(group);

  return (
    <div className="rounded-xl border overflow-hidden mt-3 first:mt-0"
      style={{ borderColor: meta.accent + '35', backgroundColor: meta.accent + '08' }}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:opacity-85 transition-opacity"
      >
        {isLive ? <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin" style={{ color: meta.accent }} />
                : <Icon className="h-4 w-4 flex-shrink-0" style={{ color: meta.accent }} />}
        <span className="text-[12.5px] font-bold" style={{ color: meta.accent }}>
          {meta.label}
        </span>
        <span className="text-[10.5px] font-mono tabular-nums" style={{ color: meta.accent, opacity: 0.7 }}>
          {tools > 0 ? `${tools} tool call${tools !== 1 ? 's' : ''}` : `${total} step${total !== 1 ? 's' : ''}`}
        </span>
        <div className="flex-1" />
        {open ? <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" style={{ color: meta.accent }} />
              : <ChevronRight className="h-3.5 w-3.5 flex-shrink-0" style={{ color: meta.accent }} />}
      </button>
      {open && (
        <div className="px-2 pb-2 space-y-0.5">
          {group.events.map(ev => <EventWidget key={ev.id} event={ev} />)}
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
// No filter bar, no external trace link — grouped into a clearly separate,
// collapsible card per agent phase, with only the thinking + tool-call feed
// inside each.

interface TraceViewerProps {
  events: AgentEvent[];
  className?: string;
  active?: boolean; // run still in progress -- the LAST phase group gets a spinner
}

export function TraceViewer({ events, className, active }: TraceViewerProps) {
  const visible = events.filter(ev => VISIBLE_KINDS.has(ev.kind));

  if (visible.length === 0) {
    return (
      <p className="text-center py-8 text-sm" style={{ color: '#c0b8b0' }}>
        No activity yet.
      </p>
    );
  }

  const groups = groupByPhase(visible);

  // Open the LAST occurrence of every phase (latest propose, latest review,
  // approved/executed/context_update/analytics), not just the single last
  // group in the array. A rework loop can produce many propose/review
  // cycles -- with only the very last group auto-open, a run that ends on
  // e.g. "approved" hid its own proposal/review content behind several
  // collapsed earlier sections with no visual hint they held anything.
  const lastOccurrenceByKey: Record<string, number> = {};
  for (const g of groups) lastOccurrenceByKey[g.key] = g.occurrence;

  return (
    <div className={className}>
      {groups.map((group, i) => (
        <PhaseSection
          key={`${group.key}-${group.occurrence}`}
          group={group}
          isLive={!!active && i === groups.length - 1}
          defaultOpen={group.occurrence === lastOccurrenceByKey[group.key]}
        />
      ))}
    </div>
  );
}
