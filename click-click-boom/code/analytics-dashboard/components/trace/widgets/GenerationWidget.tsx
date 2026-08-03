'use client';
import { useState } from 'react';
import { ExternalLink, Brain } from 'lucide-react';
import { BaseWidget } from '../BaseWidget';
import { prettyJSON, truncate } from '../utils';
import type { AgentEvent } from '../types';

interface Props {
  event: AgentEvent;
  defaultOpen?: boolean;
}

// Reasoning is shown as a SUBTLE whisper — it's the model's chain-of-thought,
// not the headline finding. Small, muted, collapsed by default.
function ReasoningBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines   = text.trim().split('\n');
  const preview = lines.slice(0, 3).join('\n');
  const isLong  = lines.length > 3;

  return (
    <div className="rounded-r-lg overflow-hidden" style={{ borderLeft: '2px solid #c4b5fd', backgroundColor: '#faf7ff' }}>
      <div className="px-3 pt-2 pb-1.5">
        <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest" style={{ color: '#8b5cf6' }}>
          <Brain className="h-2.5 w-2.5" /> model reasoning
        </span>
        <pre className="mt-1 text-[11.5px] leading-relaxed whitespace-pre-wrap font-sans"
          style={{ color: '#6d28d9', opacity: 0.8 }}>
          {expanded ? text.trim() : preview}
          {isLong && !expanded && <span style={{ color: '#a78bfa' }}>{'\n'}…</span>}
        </pre>
        {isLong && (
          <button onClick={() => setExpanded(v => !v)}
            className="text-[10px] mt-0.5 hover:opacity-70 transition-opacity"
            style={{ color: '#7c3aed' }}>
            {expanded ? 'collapse ▲' : `read more (${lines.length} lines) ▼`}
          </button>
        )}
      </div>
    </div>
  );
}

function TokenBar({ usage }: { usage: AgentEvent['usage'] }) {
  if (!usage) return null;
  const total = usage.total ?? ((usage.input ?? 0) + (usage.output ?? 0) + (usage.reasoning ?? 0));
  if (!total) return null;

  const segments = [
    { label: 'input',     val: usage.input ?? 0,     color: '#bfdbfe' },
    { label: 'reasoning', val: usage.reasoning ?? 0, color: '#ddd6fe' },
    { label: 'output',    val: usage.output ?? 0,    color: '#a7f3d0' },
  ].filter(s => s.val > 0);

  return (
    <div className="space-y-1">
      {/* stacked bar */}
      <div className="h-1.5 rounded-full overflow-hidden flex" style={{ backgroundColor: '#f0ece6' }}>
        {segments.map(s => (
          <div key={s.label} className="h-full" style={{ width: `${Math.round(s.val / total * 100)}%`, backgroundColor: s.color }} />
        ))}
      </div>
      {/* legend */}
      <div className="flex items-center gap-3 text-[10px]" style={{ color: '#9c9088' }}>
        {segments.map(s => (
          <span key={s.label} className="flex items-center gap-1">
            <span className="h-1.5 w-3 rounded-full inline-block" style={{ backgroundColor: s.color }} />
            {s.label} {s.val.toLocaleString()}
          </span>
        ))}
        <span className="ml-auto font-semibold">{total.toLocaleString()} tok</span>
      </div>
    </div>
  );
}

export function GenerationWidget({ event, defaultOpen }: Props) {
  const [showOutput, setShowOutput] = useState(false);

  const agentLabel = event.agent ?? event.step?.split('_')[0] ?? 'agent';
  const outputStr  = typeof event.output === 'string'
    ? event.output
    : prettyJSON(event.output);
  const outputPreview = truncate(outputStr.replace(/\s+/g, ' '), 100);

  // The caller-derived reasoning summary (from agent's own JSON rationale)
  const callerReasoning = event.reasoning;
  // Raw model chain-of-thought
  const modelReasoning  = event.model_reasoning;

  const tokenCount = event.usage?.total;

  return (
    <BaseWidget
      family="generation"
      title={agentLabel}
      meta={tokenCount ? `${tokenCount.toLocaleString()} tok` : undefined}
      defaultOpen={defaultOpen}
      collapsedPreview={callerReasoning ? <span className="italic">{truncate(callerReasoning, 60)}</span> : undefined}
    >
      <div className="p-3.5 space-y-3">
        {/* Caller reasoning — slightly more prominent, it's the agent's own stated rationale */}
        {callerReasoning && (
          <div className="rounded-lg px-3 py-2.5 text-sm leading-relaxed"
            style={{ backgroundColor: '#eef2ff', color: '#3730a3', border: '1px solid #c7d2fe' }}>
            <span className="text-[9px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#4f46e5' }}>
              agent's stated rationale
            </span>
            {callerReasoning}
          </div>
        )}

        {/* Model reasoning — subtle, muted, whisper treatment */}
        {modelReasoning && <ReasoningBlock text={modelReasoning} />}

        {/* Output */}
        <div>
          <button
            onClick={() => setShowOutput(v => !v)}
            className="flex items-center justify-between w-full text-left px-3 py-2 rounded-lg border hover:opacity-80 transition-opacity"
            style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#4a4540' }}>
              output JSON
            </span>
            <span className="text-[11px] font-mono truncate max-w-xs" style={{ color: '#9c9088' }}>
              {outputPreview}
            </span>
            <span className="text-[10px] ml-2" style={{ color: '#c0b8b0' }}>
              {showOutput ? '▲' : '▼'}
            </span>
          </button>
          {showOutput && (
            <pre className="mt-1.5 text-[11px] p-3 rounded-lg overflow-x-auto overflow-y-auto max-h-96 font-mono"
              style={{ backgroundColor: '#0f0e0c', color: '#e8e4df', border: '1px solid #2d2a20' }}>
              {outputStr}
            </pre>
          )}
        </div>

        {/* Token usage */}
        {event.usage && <TokenBar usage={event.usage} />}
      </div>
    </BaseWidget>
  );
}
