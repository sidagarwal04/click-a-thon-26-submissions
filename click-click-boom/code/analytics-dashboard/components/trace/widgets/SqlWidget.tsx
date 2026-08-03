'use client';
import { useState } from 'react';
import { FileText } from 'lucide-react';
import { BaseWidget } from '../BaseWidget';
import { highlightSQL, fmtMs, truncate } from '../utils';
import type { SqlOutput } from '../types';

interface Props {
  step: string;
  input?: unknown;
  output?: unknown;
  defaultOpen?: boolean;
}

export function SqlWidget({ step, input, output, defaultOpen }: Props) {
  const [showFullSQL, setShowFullSQL] = useState(false);
  const [showAllRows, setShowAllRows] = useState(false);

  const sql: string = (typeof input === 'string' ? input : (input as any)?.query ?? '').trim();
  const out = output as SqlOutput | null;

  const columns  = out?.columns ?? [];
  const rows     = out?.rows ?? out?.preview ?? [];
  const rowCount = out?.row_count ?? rows.length;
  const execMs   = out?.execution_time_ms;
  const scratched = !!out?.scratch_file;
  const hitCap   = !!out?.hit_cap;

  const sqlLines = sql.split('\n');
  const isLong   = sqlLines.length > 4;
  const preview  = sqlLines.slice(0, 3).join('\n') + (isLong && !showFullSQL ? '\n…' : '');

  const visibleRows = showAllRows ? rows : rows.slice(0, 8);
  const error = !out && !!output;

  const meta = [
    rowCount ? `${rowCount} row${rowCount !== 1 ? 's' : ''}` : '',
    execMs != null ? fmtMs(execMs) : '',
  ].filter(Boolean).join(' · ');

  return (
    <BaseWidget
      family="sql_query"
      title={truncate(sql.replace(/\s+/g, ' '), 80)}
      meta={meta}
      error={error}
      defaultOpen={defaultOpen}
      collapsedPreview={meta}
    >
      <div className="p-3.5 space-y-3">
        {/* SQL block */}
        <div className="rounded-lg overflow-hidden border" style={{ borderColor: '#2d2a20' }}>
          <div className="flex items-center justify-between px-3 py-1.5 text-[10px] font-mono"
            style={{ backgroundColor: '#1a1714', color: '#9c9088' }}>
            <span>SQL</span>
            <button onClick={() => navigator.clipboard?.writeText(sql)}
              className="hover:opacity-70 transition-opacity">copy</button>
          </div>
          <pre
            className="px-3 py-2.5 text-xs leading-relaxed overflow-x-auto font-mono"
            style={{ backgroundColor: '#0f0e0c', color: '#e8e4df' }}
            dangerouslySetInnerHTML={{ __html: highlightSQL(showFullSQL ? sql : preview) }}
          />
          {isLong && (
            <button
              onClick={() => setShowFullSQL(v => !v)}
              className="w-full py-1 text-[11px] hover:opacity-70 transition-opacity"
              style={{ backgroundColor: '#1a1714', color: '#f59e0b' }}>
              {showFullSQL ? '▲ collapse SQL' : `▼ show ${sqlLines.length} lines`}
            </button>
          )}
        </div>

        {/* Scratch file notice */}
        {scratched && (
          <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg"
            style={{ backgroundColor: '#fffbeb', color: '#92400e' }}>
            <FileText className="h-3.5 w-3.5" />
            <span>Saved to scratch: <code className="font-mono">{out?.scratch_file}</code></span>
            <span className="ml-auto">{rowCount?.toLocaleString()} rows</span>
          </div>
        )}

        {/* Result table */}
        {columns.length > 0 && rows.length > 0 && (
          <div>
            <div className="rounded-lg overflow-hidden border" style={{ borderColor: '#e5dfd6' }}>
              <div className="overflow-x-auto max-h-72">
                <table className="text-xs w-full">
                  <thead>
                    <tr style={{ backgroundColor: '#faf8f5' }}>
                      {columns.map(col => (
                        <th key={col} className="text-left px-3 py-2 font-semibold border-b"
                          style={{ color: '#4a4540', borderColor: '#e5dfd6', whiteSpace: 'nowrap' }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((row, i) => (
                      <tr key={i} className="border-b last:border-0"
                        style={{ borderColor: '#f0ece6' }}>
                        {columns.map(col => {
                          const val = (row as any)[col];
                          const isNum = typeof val === 'number';
                          return (
                            <td key={col} className="px-3 py-1.5 font-mono"
                              style={{ color: '#1c1814', textAlign: isNum ? 'right' : 'left', whiteSpace: 'nowrap' }}>
                              {val == null ? <span style={{ color: '#c0b8b0' }}>null</span> : String(val)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > 8 && (
                <button
                  onClick={() => setShowAllRows(v => !v)}
                  className="w-full py-1.5 text-[11px] border-t hover:opacity-70 transition-opacity"
                  style={{ borderColor: '#e5dfd6', color: '#f59e0b', backgroundColor: '#fffbeb' }}>
                  {showAllRows ? '▲ show fewer' : `▼ ${rows.length - 8} more rows`}
                </button>
              )}
            </div>
            <div className="flex items-center justify-between mt-1.5 px-0.5">
              <span className="text-[10px]" style={{ color: '#c0b8b0' }}>
                {hitCap && '⚠ result capped · '}
                {rowCount?.toLocaleString()} rows{execMs != null ? ` · ${fmtMs(execMs)}` : ''}
              </span>
              <button
                onClick={() => {
                  const csv = [columns.join(','), ...rows.map(r => columns.map(c => (r as any)[c]).join(','))].join('\n');
                  navigator.clipboard?.writeText(csv);
                }}
                className="text-[10px] hover:opacity-70" style={{ color: '#9c9088' }}>
                copy CSV
              </button>
            </div>
          </div>
        )}
      </div>
    </BaseWidget>
  );
}
