'use client';
import { BaseWidget } from '../BaseWidget';
import { fmtMs } from '../utils';
import type { SchemaOutput, TablesOutput } from '../types';

// ── Describe Table ────────────────────────────────────────────────────────────

interface SchemaProps { step: string; input?: unknown; output?: unknown; defaultOpen?: boolean }

function typeStyle(type: string): { color: string; bg: string } {
  if (type.includes('LowCardinality')) return { color: '#7c3aed', bg: '#faf5ff' };
  if (type.includes('Nullable'))       return { color: '#d97706', bg: '#fffbeb' };
  if (type.includes('Array'))          return { color: '#0891b2', bg: '#f0f9ff' };
  if (type.includes('UUID'))           return { color: '#6b7280', bg: '#f9fafb' };
  if (type.includes('DateTime'))       return { color: '#16a34a', bg: '#f0fdf4' };
  if (type.includes('String'))         return { color: '#1c1814', bg: '#faf8f5' };
  if (type.match(/Int|Float|UInt/))    return { color: '#2563eb', bg: '#eff6ff' };
  return { color: '#4a4540', bg: '#faf8f5' };
}

export function SchemaWidget({ step, input, output, defaultOpen }: SchemaProps) {
  const tableName: string = (input as any)?.table_name ?? step;
  const out = output as SchemaOutput | null;
  const columns = out?.columns ?? [];
  const execMs  = out?.execution_time_ms;

  return (
    <BaseWidget
      family="schema"
      title={tableName}
      meta={`${columns.length} col${columns.length !== 1 ? 's' : ''}${execMs != null ? ` · ${fmtMs(execMs)}` : ''}`}
      defaultOpen={defaultOpen}
    >
      <div className="p-3.5">
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
          <table className="text-xs w-full">
            <thead>
              <tr style={{ backgroundColor: '#faf8f5' }}>
                {['column', 'type'].map(h => (
                  <th key={h} className="text-left px-3 py-2 font-semibold border-b capitalize"
                    style={{ color: '#4a4540', borderColor: '#e5dfd6' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {columns.map((col, i) => {
                const ts = typeStyle(col.type);
                return (
                  <tr key={i} className="border-b last:border-0" style={{ borderColor: '#f0ece6' }}>
                    <td className="px-3 py-1.5 font-mono font-medium" style={{ color: '#1c1814' }}>{col.column}</td>
                    <td className="px-3 py-1.5">
                      <span className="font-mono text-[11px] px-1.5 py-0.5 rounded"
                        style={{ color: ts.color, backgroundColor: ts.bg }}>
                        {col.type}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </BaseWidget>
  );
}

// ── List Tables ───────────────────────────────────────────────────────────────

interface TablesProps { step: string; input?: unknown; output?: unknown; defaultOpen?: boolean }

export function TablesWidget({ step, input, output, defaultOpen }: TablesProps) {
  const db: string = (input as any)?.database ?? 'atlys';
  const out = output as TablesOutput | null;
  const tables  = out?.tables ?? [];
  const execMs  = out?.execution_time_ms;
  const maxRows = Math.max(...tables.map(t => t.row_count ?? 0), 1);

  return (
    <BaseWidget
      family="tables"
      title={db}
      meta={`${tables.length} tables${execMs != null ? ` · ${fmtMs(execMs)}` : ''}`}
      defaultOpen={defaultOpen}
    >
      <div className="p-3.5">
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
          <table className="text-xs w-full">
            <thead>
              <tr style={{ backgroundColor: '#faf8f5' }}>
                {['table', 'engine', 'rows'].map(h => (
                  <th key={h} className="text-left px-3 py-2 font-semibold border-b capitalize"
                    style={{ color: '#4a4540', borderColor: '#e5dfd6' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tables.map((t, i) => (
                <tr key={i} className="border-b last:border-0" style={{ borderColor: '#f0ece6' }}>
                  <td className="px-3 py-2 font-mono font-medium" style={{ color: '#1c1814' }}>{t.table}</td>
                  <td className="px-3 py-2 text-[10px]" style={{ color: '#9c9088' }}>{t.engine}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 rounded-full overflow-hidden" style={{ backgroundColor: '#f0ece6' }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.round((t.row_count / maxRows) * 100)}%`, backgroundColor: '#f59e0b' }} />
                      </div>
                      <span className="font-mono text-[11px]" style={{ color: '#4a4540' }}>
                        {t.row_count?.toLocaleString() ?? '—'}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </BaseWidget>
  );
}
