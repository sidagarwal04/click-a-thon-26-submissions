'use client';
import { useState } from 'react';
import { BaseWidget } from '../BaseWidget';
import { highlightPython, fmtMs, truncate } from '../utils';
import type { PythonOutput } from '../types';

interface Props {
  step: string;
  input?: unknown;
  output?: unknown;
  defaultOpen?: boolean;
}

export function PythonWidget({ step, input, output, defaultOpen }: Props) {
  const [showFull, setShowFull] = useState(false);

  const code: string = (typeof input === 'string' ? input : (input as any)?.code ?? '').trim();
  const out = output as PythonOutput | null;

  const exitOk  = out?.exit_code === 0 || out?.exit_code == null;
  const stdout  = out?.stdout ?? '';
  const stderr  = out?.stderr ?? '';
  const lines   = code.split('\n');
  const isLong  = lines.length > 5;
  const preview = lines.slice(0, 4).join('\n') + (isLong && !showFull ? '\n…' : '');

  return (
    <BaseWidget
      family="python"
      title={truncate(code.replace(/\s+/g, ' '), 70)}
      meta={exitOk ? 'exit 0' : `exit ${out?.exit_code}`}
      error={!exitOk}
      defaultOpen={defaultOpen}
    >
      <div className="p-3.5 space-y-3">
        {/* Code block */}
        <div className="rounded-lg overflow-hidden border" style={{ borderColor: '#1a2e1a' }}>
          <div className="flex items-center justify-between px-3 py-1.5 text-[10px] font-mono"
            style={{ backgroundColor: '#0f1f0f', color: '#6b7280' }}>
            <span>Python</span>
            <button onClick={() => navigator.clipboard?.writeText(code)}
              className="hover:opacity-70">copy</button>
          </div>
          <pre
            className="px-3 py-2.5 text-xs leading-relaxed overflow-x-auto font-mono"
            style={{ backgroundColor: '#0b160b', color: '#e8e4df' }}
            dangerouslySetInnerHTML={{ __html: highlightPython(showFull ? code : preview) }}
          />
          {isLong && (
            <button onClick={() => setShowFull(v => !v)}
              className="w-full py-1 text-[11px] hover:opacity-70"
              style={{ backgroundColor: '#0f1f0f', color: '#22c55e' }}>
              {showFull ? '▲ collapse' : `▼ show ${lines.length} lines`}
            </button>
          )}
        </div>

        {/* stdout */}
        {stdout && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: '#16a34a' }}>stdout</p>
            <pre className="text-xs p-3 rounded-lg overflow-x-auto overflow-y-auto max-h-48 font-mono"
              style={{ backgroundColor: '#f0fdf4', color: '#14532d', border: '1px solid #bbf7d0' }}>
              {stdout}
            </pre>
            {out?.truncated && <p className="text-[10px] mt-1" style={{ color: '#9c9088' }}>⚠ output truncated</p>}
          </div>
        )}

        {/* stderr */}
        {stderr && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: '#dc2626' }}>stderr</p>
            <pre className="text-xs p-3 rounded-lg overflow-x-auto overflow-y-auto max-h-48 font-mono"
              style={{ backgroundColor: '#fef2f2', color: '#7f1d1d', border: '1px solid #fecaca' }}>
              {stderr}
            </pre>
          </div>
        )}
      </div>
    </BaseWidget>
  );
}
